"""
Perform health checks on all services.
Scheduled: every 6 hours (see .github/workflows/health-check.yml)

Checks the production API, and (when SUPABASE_URL / SUPABASE_KEY are set) that alpha's daily run
has produced data recently. A failure exits non-zero and posts to Slack when SLACK_WEBHOOK is set.
"""

import os
import sys
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()


def expected_latest_day(today: date) -> date:
    """The most recent weekday before ``today``: alpha must have loaded at least that day.

    The daily run is Mon-Fri at 12:30 UTC. Checking against the previous weekday (not today) means
    a check at 06:00 UTC, before that day's run, does not raise a false alarm.
    """
    day = today - timedelta(days=1)
    while day.weekday() >= 5:  # Saturday / Sunday
        day -= timedelta(days=1)
    return day


def check_api(api_url: str) -> str | None:
    """Error text, or None when the API answers."""
    try:
        r = httpx.get(f"{api_url}/api/v1/health", timeout=10)
        r.raise_for_status()
        print(f"✓ API health check passed: {r.json()}")
        return None
    except Exception as e:  # noqa: BLE001
        return f"API health check failed: {e}"


def check_alpha_data(url: str, key: str, today: date) -> str | None:
    """Error text, or None when ``daily_metrics`` has a row from the last expected day."""
    try:
        r = httpx.get(
            f"{url}/rest/v1/daily_metrics",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "date", "order": "date.desc", "limit": "1"},
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json()
    except Exception as e:  # noqa: BLE001
        return f"alpha data check failed: {e}"
    if not rows:
        return "alpha data check failed: daily_metrics is empty"
    latest = date.fromisoformat(str(rows[0]["date"])[:10])
    expected = expected_latest_day(today)
    if latest < expected:
        return f"alpha data is stale: latest daily_metrics day is {latest}, expected {expected}+"
    print(f"✓ alpha data is fresh: latest daily_metrics day {latest}")
    return None


def notify(message: str) -> None:
    webhook = os.getenv("SLACK_WEBHOOK")
    if not webhook:
        return
    try:
        httpx.post(webhook, json={"text": f"Health check: {message}"}, timeout=10)
    except Exception:  # noqa: BLE001 - an alert failure must not hide the original error
        pass


def main() -> int:
    errors = []
    err = check_api(os.getenv("API_URL", "http://localhost:8000"))
    if err:
        errors.append(err)

    url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if url and key:
        err = check_alpha_data(url, key, date.today())
        if err:
            errors.append(err)
    else:
        print("- alpha data check skipped (SUPABASE_URL / SUPABASE_KEY not set)")

    if errors:
        for e in errors:
            print(f"✗ {e}")
        notify("; ".join(errors))
        return 1
    print("✓ All health checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
