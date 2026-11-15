"""
Retention job: keep the free Supabase database (500 MB) from filling up.
Scheduled: weekly (Sunday), see .github/workflows/prune-data.yml.

Deletes only data that is no longer useful:
  * ``options``            contracts whose expiry has passed
  * alpha daily tables     rows older than ALPHA_RETENTION_DAYS (default 180)
  * ``weekly_picks``       picks older than PICKS_RETENTION_DAYS (default 365)
  * ``screener_history``   rows older than HISTORY_RETENTION_DAYS (default 180)
Never touches trades, portfolios, audit_events, signal_log, ticker_universe or alpha_state.
Set PRUNE_DRY_RUN=1 to only report what would be deleted.
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DRY_RUN = os.getenv("PRUNE_DRY_RUN", "").lower() in {"1", "true", "yes"}

ALPHA_DAYS = int(os.getenv("ALPHA_RETENTION_DAYS", "180"))
PICKS_DAYS = int(os.getenv("PICKS_RETENTION_DAYS", "365"))
HISTORY_DAYS = int(os.getenv("HISTORY_RETENTION_DAYS", "180"))

ALPHA_TABLES = ("daily_metrics", "option_scores", "bands", "weekly_watchlist")


def plan(today: date, now: datetime) -> list[tuple[str, str, str]]:
    """(table, column, ``lt.<cutoff>`` filter) for every prune rule."""
    alpha_cut = (today - timedelta(days=ALPHA_DAYS)).isoformat()  # alpha ``date`` is TEXT YYYY-MM-DD
    rules = [("options", "expiry", f"lt.{today.isoformat()}")]
    rules += [(t, "date", f"lt.{alpha_cut}") for t in ALPHA_TABLES]
    rules.append(("weekly_picks", "week_of", f"lt.{(today - timedelta(days=PICKS_DAYS)).isoformat()}"))
    rules.append(
        ("screener_history", "created_at", f"lt.{(now - timedelta(days=HISTORY_DAYS)).isoformat()}")
    )
    return rules


def main() -> int:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("SUPABASE_URL and SUPABASE_KEY are required", file=sys.stderr)
        return 1
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Prefer": "count=exact",
    }
    failures = 0
    with httpx.Client(timeout=60) as client:
        for table, column, flt in plan(date.today(), datetime.now(timezone.utc)):
            url = f"{SUPABASE_URL}/rest/v1/{table}"
            try:
                if DRY_RUN:
                    r = client.head(url, headers=headers, params={column: flt})
                else:
                    r = client.delete(url, headers=headers, params={column: flt})
                if r.status_code == 404:  # table not created in this project (e.g. no alpha yet)
                    print(f"  - {table}: not present, skipped")
                    continue
                r.raise_for_status()
                count = r.headers.get("content-range", "*/?").split("/")[-1]
                verb = "would delete" if DRY_RUN else "deleted"
                print(f"  ✓ {table}: {verb} rows where {column} {flt} (matched: {count})")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  ✗ {table}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
