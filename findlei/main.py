"""
FindLEI  –  FastAPI backend
=============================
Endpoints
---------
POST /api/upload              Upload Excel; returns job_id + preview
POST /api/process/{job_id}    Start async LEI batch check
GET  /api/stream/{job_id}     SSE stream (real-time progress)
GET  /api/status/{job_id}     Poll-based status + results
GET  /api/download/{job_id}   Download enriched Excel
GET  /                        Serve frontend (static/index.html)
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from excel_handler import ExcelReadError, read_lei_from_excel, write_results_to_excel
from lei_checker import check_lei_batch

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("findlei.main")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="FindLEI API",
    description="LEI batch lookup for banking compliance",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store (replace with Redis for multi-worker deployments) ─────
# jobs[job_id] = {
#   status:       "pending" | "processing" | "completed" | "error"
#   leis:         List[str]
#   results:      List[dict]
#   progress:     int  (count resolved so far)
#   error_msg:    str
#   original_bytes: bytes
#   filename:     str
#   column_info:  dict
# }
jobs: Dict[str, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_job(job_id: str) -> dict:
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_excel(file: UploadFile = File(...)):
    """
    Receive an Excel file, detect the LEI column, return a job_id + preview.
    """
    allowed_exts = {".xlsx", ".xlsm", ".xls", ".ods"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Use .xlsx, .ods or .xls",
        )

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:   # 50 MB guard
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    try:
        leis, column_info = read_lei_from_excel(content, file.filename)
    except ExcelReadError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not leis:
        raise HTTPException(status_code=422, detail="No LEI codes found in the file")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status":         "pending",
        "leis":           leis,
        "results":        [],
        "progress":       0,
        "error_msg":      "",
        "original_bytes": content,
        "filename":       file.filename,
        "column_info":    column_info,
    }

    # Filter out blanks/invalids for display
    non_blank = [l for l in leis if l.strip()]
    logger.info("Job %s created: %d LEIs from '%s'", job_id, len(non_blank), file.filename)

    return {
        "job_id":    job_id,
        "lei_count": len(non_blank),
        "filename":  file.filename,
        "preview":   non_blank[:8],
    }


@app.post("/api/process/{job_id}")
async def start_processing(job_id: str, background_tasks: BackgroundTasks):
    """Kick off the background LEI-checking task."""
    job = _get_job(job_id)
    if job["status"] not in ("pending",):
        raise HTTPException(status_code=409, detail=f"Job is already {job['status']}")

    job["status"] = "processing"
    background_tasks.add_task(_run_job, job_id)
    return {"status": "processing", "job_id": job_id}


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    """Poll-based status endpoint."""
    job = _get_job(job_id)
    non_blank_total = len([l for l in job["leis"] if l.strip()])
    return {
        "status":    job["status"],
        "progress":  job["progress"],
        "total":     non_blank_total,
        "results":   job["results"],
        "error_msg": job.get("error_msg", ""),
    }


@app.get("/api/stream/{job_id}")
async def stream_progress(job_id: str):
    """
    Server-Sent Events stream.
    Each event carries: status, progress, total, latest_result.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def generator():
        while True:
            job = jobs.get(job_id)
            if job is None:
                break

            non_blank_total = len([l for l in job["leis"] if l.strip()])
            payload = {
                "status":        job["status"],
                "progress":      job["progress"],
                "total":         non_blank_total,
                "latest_result": job["results"][-1] if job["results"] else None,
                "error_msg":     job.get("error_msg", ""),
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if job["status"] in ("completed", "error"):
                break

            await asyncio.sleep(0.6)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",   # disables nginx proxy buffering
        },
    )


@app.get("/api/download/{job_id}")
async def download_results(job_id: str):
    """Return the enriched Excel file."""
    job = _get_job(job_id)
    if job["status"] != "completed":
        raise HTTPException(status_code=409, detail="Job not completed yet")
    if not job["results"]:
        raise HTTPException(status_code=422, detail="No results to export")

    try:
        out_bytes = write_results_to_excel(
            job["original_bytes"],
            job["results"],
            job["column_info"],
        )
    except Exception as exc:
        logger.exception("Excel write error for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Excel write failed: {exc}")

    stem   = Path(job["filename"]).stem
    suffix = Path(job["filename"]).suffix or ".xlsx"
    dl_name = f"{stem}_LEI_results{suffix}"

    return Response(
        content=out_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{dl_name}"'},
    )


# ── Background task ───────────────────────────────────────────────────────────
async def _run_job(job_id: str):
    job = jobs[job_id]
    try:
        def on_progress(idx: int, result: dict):
            job["progress"] = idx + 1
            job["results"].append(result)

        await check_lei_batch(job["leis"], on_progress=on_progress)
        job["status"] = "completed"
        logger.info("Job %s completed: %d results", job_id, len(job["results"]))

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        job["status"]    = "error"
        job["error_msg"] = str(exc)


# ── Static frontend ───────────────────────────────────────────────────────────
STATIC_DIR = Path(__file__).parent / "static"

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

# Mount remaining static assets (CSS, JS, icons)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
