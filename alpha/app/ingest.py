"""
Alpha Option Trading System — free data ingestion.

Fetches today's screener metrics from yfinance (no API key) through
``data_sources/free_metrics.py`` and returns them as a DataFrame in the screener's column names.
``main.py`` scores and stores the rows (set ``INGEST_LIVE=1`` to use this as the data source).

The universe is capped (``INGEST_MAX_TICKERS``, default 100) so a run fits free tiers. Polygon,
FMP and Massive are not used here; add them later if a paid source is chosen
(docs/TODO/PENDING.md item 6).
"""

import os

import pandas as pd

from app.data_sources.free_metrics import fetch_metrics, realized_vol_30d  # noqa: F401
from app.data_sources.ticker_universe import load_tickers

DEFAULT_MAX_TICKERS = 100


def resolve_universe(fresh: list[str]) -> list[str]:
    """Tickers to ingest: today's fresh list, applied to the stored master list as a diff.

    The first run stores the whole list (the one-time bulk load). After that only tickers that
    were added or dropped since last time are written. The stored active list is what gets
    ingested, so a failed list fetch falls back to the stored one instead of an empty run. If the
    database cannot be reached the fresh list is used as is and nothing is stored.
    """
    try:
        from app.database.universe import active_tickers, sync_universe

        plan = sync_universe(fresh)
        print(f"Universe sync: {plan.summary()}")
        if plan.removal_skipped:
            print(f"[WARNING] Removals skipped: {plan.removal_skipped}")
        active = active_tickers()
        if active:
            return active
    except Exception as e:  # noqa: BLE001 - never block a run on the bookkeeping
        print(f"[WARNING] Could not sync the ticker universe ({e}); using the fresh list.")
    return fresh


def run_ingestion_pipeline(tickers: list[str] | None = None) -> pd.DataFrame:
    """Fetch metrics for ``tickers`` (or the capped universe) and return one row per ticker."""
    if tickers is None:
        fresh = load_tickers(
            use_sp500=True,
            use_nasdaq100=True,
            use_most_active=False,  # that source needs an FMP key
            use_custom=True,
            max_total=int(os.getenv("INGEST_MAX_TICKERS", DEFAULT_MAX_TICKERS)),
        )
        tickers = resolve_universe(fresh)
    print(f"Ingesting {len(tickers)} tickers from yfinance...")
    df = fetch_metrics(tickers)
    print(f"Fetched {len(df)} of {len(tickers)} tickers.")
    return df


if __name__ == "__main__":
    print(run_ingestion_pipeline().head())
