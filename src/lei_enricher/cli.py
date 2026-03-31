"""
lei_enricher.cli
~~~~~~~~~~~~~~~~
Headless CLI for batch LEI enrichment.
Works without PySide6 — safe for servers and web-app backends.

Usage:
    lei-enrich input.xlsx --output enriched.xlsx [--lei-col LEI] [--sheet Sheet1] [--fallback]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import GleifClient, LeiLookupFallback, LeiResult, chunked, is_valid_lei, normalize_lei
from .cache import LeiCache
from .io_excel import read_table, write_table


def enrich_dataframe(
    df,
    *,
    lei_col: str | None = None,
    status_col: str = "Entity Status",
    renewal_col: str = "Next Renewal Date",
    cache_db: str | None = None,
    cache_days: int = 14,
    gleif_batch_size: int = 200,
    gleif_throttle_s: float = 0.2,
    fallback_enabled: bool = False,
    fallback_throttle_s: float = 1.0,
    progress_callback=None,
):
    """
    Pure-Python enrichment function — no GUI, no threads.
    Call this from Flask/FastAPI/Celery/scripts.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe with a LEI column.
    lei_col : str, optional
        Name of the LEI column. Auto-detected if None.
    status_col : str
        Output column name for Entity Status.
    renewal_col : str
        Output column name for Next Renewal Date.
    cache_db : str, optional
        Path to SQLite cache file. Defaults to ~/lei_cache.sqlite.
    cache_days : int
        Cache TTL in days.
    gleif_batch_size : int
        Max LEIs per GLEIF API batch request.
    gleif_throttle_s : float
        Seconds to wait between GLEIF batches.
    fallback_enabled : bool
        If True, query lei-lookup.com for GLEIF misses.
    fallback_throttle_s : float
        Seconds to wait between fallback requests.
    progress_callback : callable(done, total), optional
        Called after each batch.

    Returns
    -------
    pd.DataFrame
        Enriched dataframe with status_col and renewal_col added/updated.
    """
    # Auto-detect LEI column
    if lei_col is None or lei_col not in df.columns:
        for c in df.columns:
            if str(c).strip().lower() in {"lei", "lei_number", "lei number", "lei code"}:
                lei_col = c
                break
        if lei_col is None:
            for c in df.columns:
                if "lei" in str(c).strip().lower():
                    lei_col = c
                    break
    if lei_col is None:
        raise ValueError("Cannot find LEI column. Specify --lei-col or ensure column contains 'lei'.")

    # Ensure output columns exist
    if status_col not in df.columns:
        df[status_col] = None
    if renewal_col not in df.columns:
        df[renewal_col] = None

    # Reorder: output cols immediately after LEI col
    cols = list(df.columns)
    lei_idx = cols.index(lei_col)
    cols.remove(status_col)
    cols.remove(renewal_col)
    cols = cols[: lei_idx + 1] + [status_col, renewal_col] + cols[lei_idx + 1 :]
    df = df[cols].copy()

    df[lei_col] = df[lei_col].map(normalize_lei)
    unique_leis = [x for x in df[lei_col].dropna().unique().tolist() if is_valid_lei(x)]
    unique_leis.sort()

    total = len(unique_leis)
    done = 0

    if cache_db is None:
        cache_db = str(Path.home() / "lei_cache.sqlite")

    cache = LeiCache(cache_db)
    gleif = GleifClient(throttle_s=gleif_throttle_s)
    fallback = LeiLookupFallback(throttle_s=fallback_throttle_s)

    results: dict[str, LeiResult] = {}

    # Cache pass
    for lei in unique_leis:
        c = cache.get(lei, cache_days)
        if c:
            results[lei] = LeiResult(c.entity_status, c.next_renewal_date, source="cache")

    to_fetch = [lei for lei in unique_leis if lei not in results]

    # GLEIF batches
    for batch in chunked(to_fetch, gleif_batch_size):
        batch_res = gleif.lookup_batch(batch)
        for lei, res in batch_res.items():
            results[lei] = res
            cache.put(lei, res.entity_status, res.next_renewal_date, res.source or "gleif")
        done = min(total, len(results))
        if progress_callback:
            progress_callback(done, total)

    # Fallback for misses
    misses = [
        lei
        for lei in to_fetch
        if not results.get(lei) or (not results[lei].entity_status and not results[lei].next_renewal_date)
    ]
    if fallback_enabled and misses:
        for i, lei in enumerate(misses, start=1):
            res = fallback.lookup(lei)
            existing = results.get(lei, LeiResult())
            merged = LeiResult(
                entity_status=existing.entity_status or res.entity_status,
                next_renewal_date=existing.next_renewal_date or res.next_renewal_date,
                source=res.source if (res.entity_status or res.next_renewal_date) else (existing.source or res.source),
            )
            results[lei] = merged
            cache.put(lei, merged.entity_status, merged.next_renewal_date, merged.source or "lei-lookup")
            if progress_callback:
                progress_callback(done + i, total)

    # Write results back
    df[status_col] = df[lei_col].map(
        lambda x: results[x].entity_status if isinstance(x, str) and x in results else None
    )
    df[renewal_col] = df[lei_col].map(
        lambda x: results[x].next_renewal_date if isinstance(x, str) and x in results else None
    )

    return df


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lei-enrich",
        description="Batch-enrich LEI codes from an Excel/CSV file using the GLEIF API.",
    )
    parser.add_argument("input", help="Input file (.xlsx, .csv, .ods)")
    parser.add_argument("--output", "-o", help="Output file (default: <input>_enriched.xlsx)")
    parser.add_argument("--lei-col", default=None, help="Name of the LEI column (auto-detected if omitted)")
    parser.add_argument("--sheet", default=None, help="Sheet name (Excel/ODS only)")
    parser.add_argument("--fallback", action="store_true", help="Enable fallback to lei-lookup.com for misses")
    parser.add_argument("--cache-days", type=int, default=14, help="Cache TTL in days (default: 14)")
    args = parser.parse_args()

    in_path = args.input
    out_path = args.output
    if not out_path:
        p = Path(in_path)
        out_path = str(p.with_name(p.stem + "_enriched.xlsx"))

    print(f"Reading: {in_path}")
    from .io_excel import read_table, write_table

    df = read_table(in_path, sheet=args.sheet)

    def progress(done, total):
        print(f"  Progress: {done}/{total}", end="\r", flush=True)

    df = enrich_dataframe(
        df,
        lei_col=args.lei_col,
        cache_days=args.cache_days,
        fallback_enabled=args.fallback,
        progress_callback=progress,
    )

    write_table(df, out_path)
    print(f"\nDone. Saved: {out_path}")


if __name__ == "__main__":
    main()
