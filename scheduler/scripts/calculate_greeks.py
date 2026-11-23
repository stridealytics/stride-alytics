"""
Calculate option Greeks for tracked symbols and store them in Supabase.
Scheduled: Mon-Fri @ 21:00 UTC (after the US close in both EST and EDT).

Reads the cached chain rows from the ``options`` table, recomputes Black-Scholes Greeks from the
**underlying's** spot price (one yfinance call per symbol) and writes them back in one batched
upsert per symbol. Exits non-zero when nothing could be updated, so a broken run is not green.
"""

import os
import sys
from datetime import date

import httpx
from dotenv import load_dotenv

# Add backend to path so we can reuse the Greeks engine (pure maths, no scipy)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Tracked symbols
TRACKED_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "AMD"]
BATCH_SIZE = 200


def underlying_spot(symbol: str) -> float | None:
    """Latest price of the underlying (NOT the option's own price)."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info["last_price"]
        if price and price > 0:
            return float(price)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as exc:  # noqa: BLE001
        print(f"    ⚠️ {symbol}: spot unavailable: {exc}")
    return None


def compute_updates(rows: list[dict], spot: float, today: date) -> list[dict]:
    """Greeks payloads (keyed by the primary key) for every usable contract row."""
    from app.services.greeks import calculate_greeks

    updates: list[dict] = []
    for opt in rows:
        try:
            strike = float(opt["strike"])
            iv = opt.get("implied_vol")
            if strike <= 0 or not iv or float(iv) <= 0:
                continue  # no implied vol -> no honest Greeks; never invent one
            days = (date.fromisoformat(str(opt["expiry"])[:10]) - today).days
            if days <= 0:
                continue
            g = calculate_greeks(
                spot=spot,
                strike=strike,
                time_to_expiry=days / 365.0,
                volatility=float(iv),
                option_type=opt["option_type"],
            )
        except (KeyError, ValueError, TypeError):
            continue
        updates.append(
            {
                "symbol": opt["symbol"],
                "strike": opt["strike"],
                "expiry": opt["expiry"],
                "option_type": opt["option_type"],
                "delta": g.delta,
                "gamma": g.gamma,
                "theta": g.theta,
                "vega": g.vega,
                "rho": g.rho,
                "updated_at": today.isoformat(),
            }
        )
    return updates


def main() -> int:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("✗ SUPABASE_URL and SUPABASE_KEY must be set", file=sys.stderr)
        return 1

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    upsert_headers = {**headers, "Prefer": "resolution=merge-duplicates,return=minimal"}

    print(f"🚀 Calculating Greeks for {len(TRACKED_SYMBOLS)} symbols...")
    total_updated = 0
    failures = 0
    today = date.today()

    with httpx.Client(timeout=30) as client:
        for symbol in TRACKED_SYMBOLS:
            try:
                resp = client.get(
                    f"{SUPABASE_URL}/rest/v1/options",
                    headers=headers,
                    params={
                        "symbol": f"eq.{symbol}",
                        "expiry": f"gt.{today.isoformat()}",
                        "select": "symbol,strike,expiry,option_type,implied_vol",
                        "limit": 5000,
                    },
                )
                resp.raise_for_status()
                rows = resp.json()
                if not rows:
                    print(f"  → {symbol}: no data in Supabase (yet)")
                    continue

                spot = underlying_spot(symbol)
                if spot is None:
                    failures += 1
                    continue

                updates = compute_updates(rows, spot, today)
                for i in range(0, len(updates), BATCH_SIZE):
                    r = client.post(
                        f"{SUPABASE_URL}/rest/v1/options",
                        headers=upsert_headers,
                        params={"on_conflict": "symbol,strike,expiry,option_type"},
                        json=updates[i : i + BATCH_SIZE],
                    )
                    r.raise_for_status()
                total_updated += len(updates)
                print(f"  ✓ {symbol}: {len(updates)}/{len(rows)} contracts updated (spot {spot})")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"  ✗ {symbol} error: {exc}", file=sys.stderr)

    print(f"\nDone. {total_updated} contracts updated, {failures} symbol failure(s). Date: {today}")
    return 1 if (failures and total_updated == 0) or failures == len(TRACKED_SYMBOLS) else 0


if __name__ == "__main__":
    sys.exit(main())
