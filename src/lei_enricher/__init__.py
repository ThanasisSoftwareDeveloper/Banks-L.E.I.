"""
lei_enricher
~~~~~~~~~~~~
Batch-validate and enrich LEI codes via the GLEIF API.

Quick start (library usage):
    from lei_enricher import enrich_dataframe
    import pandas as pd

    df = pd.read_excel("my_leis.xlsx")
    result = enrich_dataframe(df)
    result.to_excel("enriched.xlsx", index=False)

Quick start (single LEI lookup):
    from lei_enricher import GleifClient
    client = GleifClient()
    results = client.lookup_batch(["HWUPKR0MPOU8FGXBT394"])
    print(results)
"""

from .core import (
    GleifClient,
    LeiLookupFallback,
    LeiResult,
    is_valid_lei,
    normalize_lei,
)
from .cache import LeiCache
from .io_excel import read_table, write_table
from .cli import enrich_dataframe

__all__ = [
    "GleifClient",
    "LeiLookupFallback",
    "LeiResult",
    "LeiCache",
    "is_valid_lei",
    "normalize_lei",
    "read_table",
    "write_table",
    "enrich_dataframe",
]

__version__ = "0.1.0"
