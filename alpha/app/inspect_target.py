"""Read-only report on the Supabase project alpha is pointed at.

Run: ``uv run python -m app.inspect_target``

Prints the project reference (the part of ``SUPABASE_URL`` before ``.supabase.co``; not a secret),
which alpha tables exist, how many rows they hold, the newest day of data and whether the data is
protected. It never prints keys and never writes anything, so it is safe to run against any project.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

TABLES = (
    "daily_metrics",
    "option_scores",
    "bands",
    "weekly_watchlist",
    "ticker_universe",
    "alpha_state",
    "alpha_trades",
    "alpha_audit_log",
)


def project_ref(url: str | None) -> str:
    """``https://abcd1234.supabase.co`` -> ``abcd1234`` (or the host if it is not a Supabase URL)."""
    host = urlparse(url or "").hostname or ""
    if host.endswith(".supabase.co"):
        return host.split(".")[0]
    return host or "(SUPABASE_URL not set)"


def _count(client, table: str) -> int | None:
    """Row count, or None if the table does not exist or cannot be read."""
    try:
        resp = client.table(table).select("*", count="exact").limit(1).execute()
    except Exception:  # noqa: BLE001 - a missing table is an expected answer here
        return None
    count = getattr(resp, "count", None)
    return count if count is not None else len(resp.data or [])


def inspect(client, url: str | None) -> list[str]:
    """Report lines for the project behind ``client``."""
    lines = [f"Supabase project: {project_ref(url)}"]
    expect = os.getenv("ALPHA_EXPECT_PROJECT")
    if expect:
        verdict = "matches" if expect in (url or "") else "DOES NOT MATCH"
        lines.append(f"ALPHA_EXPECT_PROJECT: {expect} ({verdict})")
    else:
        lines.append("ALPHA_EXPECT_PROJECT is not set (runs are not tied to one project).")

    for table in TABLES:
        n = _count(client, table)
        shown = "missing (run supabase_schema.sql)" if n is None else f"{n} rows"
        lines.append(f"  {table:<18} {shown}")

    try:
        query = client.table("daily_metrics").select("date").order("date", desc=True).limit(1)
        rows = query.execute().data
        newest = str(rows[0]["date"])[:10] if rows else "none"
    except Exception:  # noqa: BLE001
        newest = "unknown"
    lines.append(f"Newest daily_metrics day: {newest}")

    try:
        from app.database.safety import is_loaded

        protected = "yes" if is_loaded(client) else "no"
    except Exception:  # noqa: BLE001
        protected = "unknown (alpha_state missing?)"
    lines.append(f"Data protected (initial load complete): {protected}")
    return lines


def main() -> int:
    from app.config import config
    from app.database.supabase_client import get_supabase_client

    for line in inspect(get_supabase_client(), config.SUPABASE_URL):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
