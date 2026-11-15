import math
from datetime import date, datetime

import pandas as pd

from .supabase_client import get_supabase_client

# Column mapping from CSV format to snake_case for Supabase
CSV_TO_DB_COLUMNS = {
    "Ticker": "ticker",
    "Price": "price",
    "Avg Volume (Shares)": "avg_volume_shares",
    "Option Volume": "option_volume",
    "Max OI (Near Exp)": "max_oi_near_exp",
    "Bid-Ask Spread %": "bid_ask_spread_pct",
    "IV 30d": "iv_30d",
    "IV Rank (1y)": "iv_rank_1y",
    "HV 30d": "hv_30d",
    "ATR": "atr",
    "Next Earnings Date": "next_earnings_date",
    "Short Interest %": "short_interest_pct",
    "Revenue Growth (YoY)": "revenue_growth_yoy",
    "Debt/Equity": "debt_equity",
    "Quality Score (1-5)": "quality_score",
    "Trend (Above/Below 20/50/200 EMA)": "trend",
    "Trend": "trend",
    "Band": "band",
    "Sector": "sector",
    "Market Cap": "market_cap",
    "Beta": "beta",
    "Strategy Tag": "strategy",
}

# Tables written by the daily pipeline. Every one has a TEXT ``date`` column
# holding ``YYYY-MM-DD``.
DAILY_TABLES = ("daily_metrics", "option_scores", "bands", "weekly_watchlist")


def today_str() -> str:
    """Today's date as ``YYYY-MM-DD`` (the format stored in every ``date`` column)."""
    return pd.Timestamp.today().strftime("%Y-%m-%d")


def _convert_timestamps(obj):
    """Recursively convert Timestamps, NaN/NaT and other values to JSON-compliant types."""
    if isinstance(obj, dict):
        return {k: _convert_timestamps(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_timestamps(item) for item in obj]
    # NaN / NaT / None -> null. (pd.NaT is a datetime subclass, so check this first,
    # otherwise it would be stored as the string "NaT".)
    if obj is None or (not isinstance(obj, (str, bytes)) and pd.isna(obj)):
        return None
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, float) and math.isinf(obj):
        return None
    return obj


def clear_all_tables() -> None:
    """
    Clear all data from the daily_metrics, option_scores, bands, and weekly_watchlist tables.

    Only for resetting corrupted data in a brand-new database. Once the initial load is complete
    the data is protected and this raises ``DestructiveOperationBlockedError`` (see ``safety.py``).
    """
    from .safety import require_unlocked

    client = get_supabase_client()
    require_unlocked("clear_all_tables", client)
    for table in DAILY_TABLES:
        client.table(table).delete().neq("ticker", "").execute()
    print("[INFO] All tables cleared")


def _map_columns(df: pd.DataFrame, day: str | None = None) -> pd.DataFrame:
    """Map CSV column names to snake_case for Supabase and normalise ``date``.

    ``date`` is always ``YYYY-MM-DD``. If ``day`` is given it overrides any
    existing value so every table is written (and later deleted) under the
    same key.
    """
    result = df.copy()
    for csv_col, db_col in CSV_TO_DB_COLUMNS.items():
        if csv_col in result.columns:
            result = result.rename(columns={csv_col: db_col})

    if day is not None:
        result["date"] = day
    elif "date" in result.columns:
        result["date"] = result["date"].astype(str).str[:10]
    elif "Date" in df.columns:
        result["date"] = df["Date"].astype(str).str[:10]
    else:
        result["date"] = today_str()
    return result


# Columns that exist in the daily_metrics Supabase table (in correct order to match CSV)
DAILY_METRICS_COLUMNS = [
    "date",
    "ticker",
    "price",
    "avg_volume_shares",
    "option_volume",
    "max_oi_near_exp",
    "bid_ask_spread_pct",
    "iv_30d",
    "iv_rank_1y",
    "hv_30d",
    "atr",
    "next_earnings_date",
    "short_interest_pct",
    "revenue_growth_yoy",
    "debt_equity",
    "quality_score",
    "sector",
    "market_cap",
    "float_shares",
    "beta",
    "option_score",
    "band",
    "trend",
    "strategy",
]

OPTION_SCORE_COLUMNS = ["date", "ticker", "option_score", "trend", "strategy"]

WATCHLIST_COLUMNS = [
    "date",
    "ticker",
    "sector",
    "price",
    "option_score",
    "iv_rank_1y",
    "iv_30d",
    "next_earnings_date",
    "trend",
    "strategy",
]


def _rows(df: pd.DataFrame, columns: list[str], day: str | None = None) -> list[dict]:
    """Build JSON-safe insert rows for the given columns (those that exist)."""
    if df.empty:
        return []
    mapped = _map_columns(df, day)
    available = [c for c in columns if c in mapped.columns]
    return _convert_timestamps(mapped[available].to_dict(orient="records"))


def _band_rows(df: pd.DataFrame, day: str | None = None) -> list[dict]:
    if df.empty or "Band" not in df.columns:
        return []
    return _rows(df, ["date", "ticker", "band"], day)


PAGE = 1000
CHUNK = 500


def _same(a, b) -> bool:
    """Equal for our purposes: both empty, numerically equal, or the same text."""
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    return str(a) == str(b)


def plan_table(existing: list[dict], payload: list[dict]) -> tuple[list[dict], list[tuple]]:
    """Pure: which payload rows to insert, and which existing tickers to update (and with what).

    A row is inserted only if its ticker has no row for the day yet. For a ticker that has one,
    only the columns whose value actually changed are updated; an identical row is left alone.
    """
    by_ticker = {str(r["ticker"]).upper(): r for r in existing}
    inserts: list[dict] = []
    updates: list[tuple] = []  # (ticker, changed columns)
    for row in payload:
        current = by_ticker.get(str(row["ticker"]).upper())
        if current is None:
            inserts.append(row)
            continue
        changed = {
            c: v
            for c, v in row.items()
            if c not in ("ticker", "date") and not _same(v, current.get(c))
        }
        if changed:
            updates.append((row["ticker"], changed))
    return inserts, updates


def _fetch_day(client, table: str, day: str) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        page = (
            client.table(table)
            .select("*")
            .like("date", f"{day}%")
            .range(start, start + PAGE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        start += PAGE


def sync_day(df_bands: pd.DataFrame, weekly: pd.DataFrame, day: str | None = None) -> dict:
    """Write one day's rows by adding and updating only what is new or changed.

    Nothing is wiped: for each table the day's existing rows are read, then new tickers are
    inserted and changed rows get an update of just the changed columns. Re-running with the same
    data writes nothing. A ticker missing from today's payload keeps its row (history). The one
    exception is ``weekly_watchlist``, whose rows for tickers that dropped off today's list are
    removed one by one (never the whole day; if that would empty the day it is skipped).

    All payloads are built before anything is written, and Supabase errors are raised. In a dry run
    (``ALPHA_DRY_RUN=1``) the same report is computed from what is stored, but nothing is written.
    """
    from .safety import dry_run

    read_only = dry_run()
    day = day or today_str()
    payload = {
        "daily_metrics": _rows(df_bands, DAILY_METRICS_COLUMNS, day),
        "option_scores": _rows(df_bands, OPTION_SCORE_COLUMNS, day),
        "bands": _band_rows(df_bands, day),
        "weekly_watchlist": _rows(weekly, WATCHLIST_COLUMNS, day),
    }

    client = get_supabase_client()
    report: dict = {}
    for table in DAILY_TABLES:
        existing = _fetch_day(client, table, day)
        inserts, updates = plan_table(existing, payload[table])
        if not read_only:
            for i in range(0, len(inserts), CHUNK):
                client.table(table).insert(inserts[i : i + CHUNK]).execute()
            for ticker, changed in updates:
                client.table(table).update(changed).eq("ticker", ticker).like(
                    "date", f"{day}%"
                ).execute()

        stale = 0
        if table == "weekly_watchlist" and payload[table]:
            keep = {str(r["ticker"]).upper() for r in payload[table]}
            drop = sorted({str(r["ticker"]).upper() for r in existing} - keep)
            if drop and len(drop) < len({str(r["ticker"]).upper() for r in existing}):
                if not read_only:
                    for i in range(0, len(drop), CHUNK):
                        client.table(table).delete().in_("ticker", drop[i : i + CHUNK]).like(
                            "date", f"{day}%"
                        ).execute()
                stale = len(drop)
        report[table] = {
            "inserted": len(inserts),
            "updated": len(updates),
            "unchanged": len(payload[table]) - len(inserts) - len(updates),
            "removed": stale,
        }
    return report


def insert_daily_metrics(df: pd.DataFrame) -> None:
    """Insert row-level daily metrics into Supabase."""
    rows = _rows(df, DAILY_METRICS_COLUMNS)
    if rows:
        get_supabase_client().table("daily_metrics").insert(rows).execute()


def insert_option_scores(df: pd.DataFrame) -> None:
    """Insert ticker-level option scores into Supabase."""
    rows = _rows(df, OPTION_SCORE_COLUMNS)
    if rows:
        get_supabase_client().table("option_scores").insert(rows).execute()


def insert_bands(df: pd.DataFrame) -> None:
    """Insert band classifications into Supabase (needs a 'Band' column)."""
    rows = _band_rows(df)
    if rows:
        get_supabase_client().table("bands").insert(rows).execute()


def insert_weekly_watchlist(df: pd.DataFrame) -> None:
    """Insert weekly watchlist into Supabase."""
    rows = _rows(df, WATCHLIST_COLUMNS)
    if rows:
        get_supabase_client().table("weekly_watchlist").insert(rows).execute()


def insert_trades(df: pd.DataFrame) -> None:
    """
    Insert trades into the Supabase alpha_trades table (not the backend's ``trades``).

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with trades columns: date, ticker, strategy, entry_strikes,
        expiry, credit_debit, reason, exit_plan.
    """
    trade_cols = [
        "date",
        "ticker",
        "strategy",
        "entry_strikes",
        "expiry",
        "credit_debit",
        "reason",
        "exit_plan",
    ]
    rows = _rows(df, trade_cols)
    if rows:
        get_supabase_client().table("alpha_trades").insert(rows).execute()
