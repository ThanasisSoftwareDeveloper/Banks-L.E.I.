# LEI Enricher

**Batch-validate and enrich LEI codes** from Excel / CSV files using the [GLEIF API](https://www.gleif.org/en/lei-data/gleif-api), with optional fallback provider.

Built for KYC / AML / compliance teams who maintain spreadsheets with Legal Entity Identifiers.

---

## Features

- 🔍 **GLEIF API** — batched lookups (up to 200 LEIs per request), rate-limit friendly
- 💾 **SQLite cache** — configurable TTL (default 14 days), avoids redundant API calls
- 📊 **Excel / CSV / ODS** input & output
- 🖥️ **Desktop GUI** (PySide6) — optional, install with `[gui]`
- 🌐 **Web-app ready** — use `enrich_dataframe()` directly in Flask / FastAPI / Celery
- ⚡ **CLI** — `lei-enrich input.xlsx --output enriched.xlsx`
- 🔄 **Fallback** — optional HTML scrape of lei-lookup.com for GLEIF misses

---

## Installation

### Core (no GUI — suitable for servers & web apps)

```bash
pip install lei-enricher
```

### With Desktop GUI

```bash
pip install "lei-enricher[gui]"
```

### With ODS (LibreOffice Calc) support

```bash
pip install "lei-enricher[ods]"
```

### With Flask web backend

```bash
pip install "lei-enricher[web]"
```

### Everything

```bash
pip install "lei-enricher[all]"
```

---

## Quickstart

### As a Python library

```python
import pandas as pd
from lei_enricher import enrich_dataframe

df = pd.read_excel("my_leis.xlsx")
result = enrich_dataframe(df)
result.to_excel("enriched.xlsx", index=False)
```

### Single LEI lookup

```python
from lei_enricher import GleifClient

client = GleifClient()
results = client.lookup_batch(["HWUPKR0MPOU8FGXBT394", "5493001KJTIIGC8Y1R12"])
for lei, info in results.items():
    print(lei, info.entity_status, info.next_renewal_date)
```

### CLI

```bash
lei-enrich input.xlsx --output enriched.xlsx
lei-enrich input.xlsx --lei-col "Company LEI" --sheet "Sheet1" --fallback
```

### Desktop GUI

```bash
lei-enricher          # requires: pip install "lei-enricher[gui]"
```

### Flask web app (minimal example)

```python
from flask import Flask, request, send_file
import pandas as pd
from lei_enricher import enrich_dataframe
import io

app = Flask(__name__)

@app.post("/enrich")
def enrich():
    file = request.files["file"]
    df = pd.read_excel(file)
    result = enrich_dataframe(df)
    buf = io.BytesIO()
    result.to_excel(buf, index=False)
    buf.seek(0)
    return send_file(buf, download_name="enriched.xlsx", as_attachment=True)
```

---

## enrich_dataframe() parameters

| Parameter | Default | Description |
|---|---|---|
| `df` | — | Input DataFrame with LEI column |
| `lei_col` | auto-detect | Column name containing LEI codes |
| `status_col` | `"Entity Status"` | Output column for entity status |
| `renewal_col` | `"Next Renewal Date"` | Output column for next renewal date |
| `cache_db` | `~/lei_cache.sqlite` | SQLite cache path |
| `cache_days` | `14` | Cache TTL in days |
| `gleif_batch_size` | `200` | LEIs per GLEIF API request |
| `gleif_throttle_s` | `0.2` | Delay (seconds) between GLEIF batches |
| `fallback_enabled` | `False` | Use lei-lookup.com for GLEIF misses |
| `fallback_throttle_s` | `1.0` | Delay (seconds) between fallback requests |
| `progress_callback` | `None` | `callback(done, total)` for progress tracking |

---

## Output columns

The enriched file adds two columns immediately to the right of the LEI column:

- **Entity Status** — e.g. `ACTIVE`, `LAPSED`, `MERGED`, `RETIRED`
- **Next Renewal Date** — ISO 8601 date string, e.g. `2025-12-31`

---

## Project structure

```
src/lei_enricher/
  __init__.py     — public API
  core.py         — GleifClient, LeiLookupFallback, LeiResult
  cli.py          — enrich_dataframe() + CLI entry point
  cache.py        — SQLite cache
  io_excel.py     — Excel/CSV/ODS read & write
  gui.py          — PySide6 desktop GUI (optional)
  main.py         — GUI entry point (optional)
tests/
```

---

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
