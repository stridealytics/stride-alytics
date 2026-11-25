"""
Publish the weekly picks. Scheduled: Sundays @ 6:00 PM EST (23:00 UTC)

Alpha (``alpha/app/main.py``) is the single place that decides what a pick is: its option score,
14-day earnings buffer and band rules produce the ``weekly_watchlist`` table every weekday. This
script only copies the latest day of that list into ``weekly_picks`` (the table the app reads), so
the app can never show a pick that alpha's rules would reject. It computes nothing itself. The only
market-data call is a best-effort company-name lookup (yfinance) for display; a failed lookup leaves
the name empty and never blocks publishing.

Alpha does not choose strikes, expiries or targets, so those columns are left empty rather than
invented. The run fails (non-zero exit, so the workflow alerts) when alpha's list is missing, empty
or stale, instead of publishing an empty or outdated week.
"""

import os
import re
import sys
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")

PICKS_LIMIT = int(os.getenv("PICKS_LIMIT", "6"))
# Sunday publishes Friday's list (2 days old); allow a long weekend or a missed day on top.
MAX_LIST_AGE_DAYS = int(os.getenv("PICKS_MAX_LIST_AGE_DAYS", "5"))
MAX_OPTION_SCORE = 9  # number of scoring rules in alpha/app/screener/compute_option_score.py


def side_for(strategy: str | None) -> str:
    """Option type of the tag's lead structure: 'call' or 'put', otherwise 'stock' (neutral).

    Direction words alone mislead ("Bull Put Spread" is a put, "Bear Call Spread" is a call), so
    read the option type that follows them.
    """
    text = (strategy or "").lower()
    match = re.search(r"\b(?:bull|bear)\s+(put|call)\b", text)
    if match:
        return match.group(1)
    if "short put" in text:
        return "put"
    return "stock"


def _number(value) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def build_rationale(row: dict) -> str:
    """One readable line from alpha's own fields."""
    parts = [str(row.get("strategy") or "Screened candidate")]
    score = _number(row.get("option_score"))
    if score is not None:
        parts.append(f"option score {score:.0f}/{MAX_OPTION_SCORE}")
    iv_rank = _number(row.get("iv_rank_1y"))
    if iv_rank is not None:
        parts.append(f"IV rank {iv_rank:.0f}")
    if row.get("next_earnings_date"):
        parts.append(f"next earnings {str(row['next_earnings_date'])[:10]}")
    return "; ".join(parts)


def lookup_company_names(symbols: list[str]) -> dict[str, str]:
    """Best-effort ``{symbol: company name}`` from yfinance; symbols that fail are left out."""
    import yfinance as yf

    names: dict[str, str] = {}
    for symbol in symbols:
        try:
            info = yf.Ticker(symbol).info or {}
        except Exception as exc:  # Yahoo hiccup or unknown symbol: publish without a name
            print(f"[INFO] no company name for {symbol}: {exc}")
            continue
        name = info.get("longName") or info.get("shortName")
        if name:
            names[symbol] = str(name).strip()
    return names


def build_picks(
    rows: list[dict],
    week_of: str,
    limit: int = PICKS_LIMIT,
    names: dict[str, str] | None = None,
) -> list[dict]:
    """Top ``limit`` ``weekly_picks`` rows from alpha's watchlist rows (best option score first).

    Rows without a ticker or a price are skipped (``entry_price`` is required). ``names`` maps a
    symbol to its company name; a symbol without one gets ``company_name`` None.
    """
    names = names or {}
    usable = [r for r in rows if r.get("ticker") and _number(r.get("price")) is not None]
    usable.sort(
        key=lambda r: (_number(r.get("option_score")) or 0, _number(r.get("iv_rank_1y")) or 0),
        reverse=True,
    )
    picks = []
    for row in usable[:limit]:
        score = _number(row.get("option_score")) or 0
        symbol = str(row["ticker"]).upper()
        picks.append(
            {
                "symbol": symbol,
                "company_name": names.get(symbol),
                "side": side_for(row.get("strategy")),
                "strike": None,
                "expiry": None,
                "entry_price": round(_number(row["price"]), 2),
                "target_price": None,
                "stop_loss": None,
                "rationale": build_rationale(row),
                "confidence": round(min(1.0, max(0.0, score / MAX_OPTION_SCORE)), 2),
                "week_of": week_of,
            }
        )
    return picks


def check_fresh(day: str, today: date, max_age_days: int = MAX_LIST_AGE_DAYS) -> None:
    """Raise if alpha's latest list is older than ``max_age_days`` (alpha stopped running)."""
    age = (today - date.fromisoformat(day[:10])).days
    if age > max_age_days:
        raise RuntimeError(
            f"alpha's latest weekly_watchlist is from {day[:10]} ({age} days old, "
            f"limit {max_age_days}); not publishing stale picks"
        )


def _headers() -> dict:
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}


def fetch_latest_watchlist(client: httpx.Client) -> tuple[str, list[dict]]:
    """``(day, rows)`` for the newest day in alpha's ``weekly_watchlist`` table."""
    url = f"{SUPABASE_URL}/rest/v1/weekly_watchlist"
    latest = client.get(
        url, headers=_headers(), params={"select": "date", "order": "date.desc", "limit": "1"}
    )
    latest.raise_for_status()
    found = latest.json()
    if not found:
        raise RuntimeError("alpha's weekly_watchlist is empty; nothing to publish")
    day = str(found[0]["date"])[:10]
    rows = client.get(url, headers=_headers(), params={"select": "*", "date": f"like.{day}*"})
    rows.raise_for_status()
    return day, rows.json()


def existing_picks(client: httpx.Client, week_of: str) -> dict[str, str | None]:
    """``{symbol: company_name}`` already published for the week. ``strike`` and ``expiry`` are
    NULL, so the table's unique key cannot stop a re-run from adding duplicates; this check does."""
    resp = client.get(
        f"{SUPABASE_URL}/rest/v1/weekly_picks",
        headers=_headers(),
        params={"select": "symbol,company_name", "week_of": f"eq.{week_of}"},
    )
    resp.raise_for_status()
    return {str(r["symbol"]).upper(): r.get("company_name") for r in resp.json()}


def backfill_names(
    client: httpx.Client, week_of: str, have: dict[str, str | None], names: dict[str, str]
) -> int:
    """Fill ``company_name`` on this week's rows published without one. Returns rows updated."""
    updated = 0
    for symbol, current in have.items():
        name = names.get(symbol)
        if current or not name:
            continue
        resp = client.patch(
            f"{SUPABASE_URL}/rest/v1/weekly_picks",
            headers={**_headers(), "Content-Type": "application/json"},
            params={"symbol": f"eq.{symbol}", "week_of": f"eq.{week_of}"},
            json={"company_name": name},
        )
        resp.raise_for_status()
        updated += 1
    return updated


def main() -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("✗ SUPABASE_URL and SUPABASE_KEY must be set")
        sys.exit(1)

    today = date.today()
    week_of = (today - timedelta(days=today.weekday())).isoformat()

    with httpx.Client(timeout=15) as client:
        day, rows = fetch_latest_watchlist(client)
        check_fresh(day, today)
        picks = build_picks(rows, week_of)
        names = lookup_company_names([p["symbol"] for p in picks])
        for pick in picks:
            pick["company_name"] = names.get(pick["symbol"])
        print(f"📊 alpha list of {day}: {len(rows)} rows → top {len(picks)} for week of {week_of}")
        if not picks:
            print("✗ alpha's list has no usable rows (needs a ticker and a price)")
            sys.exit(1)

        have = existing_picks(client, week_of)
        filled = backfill_names(client, week_of, have, names)
        if filled:
            print(f"  ✎ added a company name to {filled} existing picks")
        new = [p for p in picks if p["symbol"] not in have]
        for i, pick in enumerate(picks, 1):
            mark = "already published" if pick["symbol"] in have else "new"
            print(f"  {i}. {pick['symbol']} ({pick['side']}) confidence {pick['confidence']} [{mark}]")

        if new:
            resp = client.post(
                f"{SUPABASE_URL}/rest/v1/weekly_picks",
                headers={**_headers(), "Content-Type": "application/json"},
                json=new,
            )
            if resp.status_code >= 400:
                print(f"✗ Supabase insert failed: {resp.status_code} {resp.text[:200]}")
                sys.exit(1)

    print(f"\n✓ Done. Published {len(new)} new weekly picks ({len(picks) - len(new)} already there)")
    print(f"  Week of: {week_of}")

    if SENDGRID_API_KEY:
        print("  📧 Email notification ready (SendGrid configured)")
    else:
        print("  📧 Email notification skipped (SENDGRID_API_KEY not set)")


if __name__ == "__main__":
    main()
