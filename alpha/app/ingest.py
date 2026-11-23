"""
Alpha Stock and Options Screening Pipeline — free data ingestion.

Fetches today's screener metrics from yfinance (no API key) through
``data_sources/free_metrics.py`` and returns them as a DataFrame in the screener's column names.
``main.py`` scores and stores the rows (set ``INGEST_LIVE=1`` to use this as the data source).

The universe is capped (``INGEST_MAX_TICKERS``, default 100) so a run fits free tiers. Polygon,
FMP and Massive are not used here; add them later if a paid source is chosen
(docs/TODO/PENDING-WORK.md item 6).
"""

import os

import pandas as pd

from app.data_sources.free_metrics import fetch_metrics, realized_vol_30d  # noqa: F401
from app.data_sources.ticker_universe import load_tickers

DEFAULT_MAX_TICKERS = 100
DEFAULT_MAX_FAIL_PCT = 20


def max_tickers() -> int:
    return int(os.getenv("INGEST_MAX_TICKERS", DEFAULT_MAX_TICKERS))


def cap_universe(active: list[str], fresh: list[str]) -> list[str]:
    """Keep the ingested list within ``INGEST_MAX_TICKERS``, today's fresh names first.

    The cap is applied to the fresh list, but the stored list only ever grows by additions, so a
    partial scrape (one source down) could push it past the cap and slow every later run.
    """
    limit = max_tickers()
    if len(active) <= limit:
        return active
    in_active = set(active)
    ordered = [t for t in dict.fromkeys(fresh) if t in in_active]
    ordered += sorted(in_active - set(ordered))
    print(
        f"[WARNING] The stored universe has {len(active)} active tickers, above the "
        f"INGEST_MAX_TICKERS limit of {limit}; ingesting the first {limit} only."
    )
    return ordered[:limit]


def resolve_universe(fresh: list[str]) -> list[str]:
    """Tickers to ingest: today's fresh list, applied to the stored master list as a diff.

    The first run stores the whole list (the one-time bulk load). After that only tickers that
    were added or dropped since last time are written. The stored active list is what gets
    ingested, so a failed list fetch falls back to the stored one instead of an empty run. If the
    database cannot be reached the fresh list is used as is and nothing is stored.
    """
    try:
        from app.database.universe import active_tickers, sync_universe

        from app.database.safety import dry_run

        plan = sync_universe(fresh)
        print(
            f"Universe sync{' (dry run, nothing written)' if dry_run() else ''}: {plan.summary()}"
        )
        if plan.removal_skipped:
            print(f"[WARNING] Removals skipped: {plan.removal_skipped}")
        active = active_tickers()
        if dry_run():  # nothing was written, so apply the plan to the list in memory
            active = sorted((set(active) | set(plan.add)) - set(plan.remove))
        if active:
            return cap_universe(active, fresh)
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
            max_total=max_tickers(),
        )
        tickers = resolve_universe(fresh)
    print(f"Ingesting {len(tickers)} tickers from yfinance...")
    df = fetch_metrics(tickers)
    print(f"Fetched {len(df)} of {len(tickers)} tickers.")
    check_fetch_rate(len(df), len(tickers))
    return df


def check_fetch_rate(fetched: int, requested: int) -> None:
    """Raise when too many tickers failed, so a rate-limited run is not stored as a normal day.

    The limit is ``INGEST_MAX_FAIL_PCT`` percent (default 20). ``main.py`` treats the error as a
    failed live fetch, alerts, and falls back to stored data.
    """
    if requested <= 0:
        return
    failed_pct = (requested - fetched) / requested * 100
    limit = float(os.getenv("INGEST_MAX_FAIL_PCT", DEFAULT_MAX_FAIL_PCT))
    if failed_pct > limit:
        raise RuntimeError(
            f"yfinance fetch too incomplete: {requested - fetched}/{requested} tickers failed "
            f"({failed_pct:.0f}% > {limit:.0f}% allowed)"
        )


if __name__ == "__main__":
    print(run_ingestion_pipeline().head())
