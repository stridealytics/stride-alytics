"""Daily screener metrics from yfinance alone (free, no API key).

Output columns use the screener's CSV names ("Option Volume", "IV 30d", ...). Anything that cannot
be measured is left as None, never guessed, so the scoring step reports it in ``Data Gaps``.

Proxies (documented, not exact):
- ``IV Rank (1y)``: percentile of today's 30-day realised volatility within its own 1-year range
  (yfinance has no implied-vol history).
- ``Quality Score (1-5)``: not available from free data, so it is left empty.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf

NEAR_EXPIRY_MIN_DAYS = 7  # skip expiries that are about to expire
IV_TARGET_DAYS = 30


def _num(value) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) or not math.isfinite(float(number)) else float(number)


def _rolling_hv(closes: pd.Series) -> pd.Series:
    returns = np.log(closes / closes.shift(1))
    return returns.rolling(30).std() * math.sqrt(252) * 100


def realized_vol_30d(closes) -> float | None:
    """Annualised volatility of the last 30 daily returns, in percent; None if too little data."""
    series = pd.Series(closes, dtype="float64").dropna()
    returns = np.log(series / series.shift(1)).dropna().tail(30)
    if len(returns) < 20:
        return None
    return float(returns.std() * math.sqrt(252) * 100)


def hv_rank(closes) -> float | None:
    """Where today's 30-day realised vol sits in its 1-year range, 0 to 100 (IV Rank proxy)."""
    series = pd.Series(closes, dtype="float64").dropna()
    hv = _rolling_hv(series).dropna()
    if len(hv) < 30:
        return None
    low, high = hv.min(), hv.max()
    if high == low:
        return None
    return float((hv.iloc[-1] - low) / (high - low) * 100)


def atr_14(hist: pd.DataFrame) -> float | None:
    """Average true range over 14 days, in price units."""
    if hist is None or len(hist) < 15 or not {"High", "Low", "Close"} <= set(hist.columns):
        return None
    prev_close = hist["Close"].shift(1)
    true_range = pd.concat(
        [
            hist["High"] - hist["Low"],
            (hist["High"] - prev_close).abs(),
            (hist["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    value = true_range.tail(14).mean()
    return None if pd.isna(value) else float(value)


def trend_label(closes) -> str | None:
    """'Above 20/50/200' style text: which of the 20/50/200-day EMAs price is above."""
    series = pd.Series(closes, dtype="float64").dropna()
    if len(series) < 50:
        return None
    price = series.iloc[-1]
    parts = []
    for span in (20, 50, 200):
        if len(series) < span:
            continue
        ema = series.ewm(span=span, adjust=False).mean().iloc[-1]
        parts.append(f"{'Above' if price > ema else 'Below'} {span}")
    return " / ".join(parts) if parts else None


def _pick_expiry(expiries: list[str], today: date, target_days: int) -> str | None:
    """The expiry at least NEAR_EXPIRY_MIN_DAYS out and closest to ``target_days``."""
    dated = []
    for text in expiries:
        try:
            days = (date.fromisoformat(text) - today).days
        except ValueError:
            continue
        if days >= NEAR_EXPIRY_MIN_DAYS:
            dated.append((abs(days - target_days), text))
    return min(dated)[1] if dated else None


def option_metrics(spot: float | None, calls: pd.DataFrame, puts: pd.DataFrame) -> dict:
    """Volume, open interest, spread % and ATM implied vol from one expiry's calls and puts."""
    both = pd.concat([calls, puts], ignore_index=True) if len(calls) + len(puts) else pd.DataFrame()
    if both.empty:
        return {}
    out: dict = {}
    volume = pd.to_numeric(both.get("volume"), errors="coerce").sum(min_count=1)
    if not pd.isna(volume):
        out["Option Volume"] = float(volume)
    oi = pd.to_numeric(both.get("openInterest"), errors="coerce").max()
    if not pd.isna(oi):
        out["Max OI (Near Exp)"] = float(oi)
    if spot and spot > 0 and "strike" in both:
        near = both[(both["strike"] - spot).abs() <= spot * 0.05]
        bid, ask = pd.to_numeric(near.get("bid"), errors="coerce"), pd.to_numeric(
            near.get("ask"), errors="coerce"
        )
        quoted = (bid > 0) & (ask > 0) & (ask >= bid)
        if quoted.any():
            mid = (bid[quoted] + ask[quoted]) / 2
            out["Bid-Ask Spread %"] = float(((ask[quoted] - bid[quoted]) / mid * 100).median())
        iv = pd.to_numeric(near.get("impliedVolatility"), errors="coerce")
        iv = iv[iv > 0.01]  # yfinance reports ~0 for contracts with no quote
        if len(iv):
            out["IV 30d"] = float(iv.mean())
    return out


def next_earnings(calendar) -> str | None:
    """First future earnings date from yfinance's calendar dict, as YYYY-MM-DD."""
    try:
        dates = calendar.get("Earnings Date") if calendar else None
    except AttributeError:
        return None
    for value in dates or []:
        stamp = pd.to_datetime(value, errors="coerce")
        if not pd.isna(stamp) and stamp.date() >= date.today():
            return stamp.date().isoformat()
    return None


def build_row(ticker: str, info: dict, hist: pd.DataFrame, options: dict, calendar=None) -> dict:
    """One screener row from already-fetched pieces (pure; the network calls are in fetch_row)."""
    closes = hist["Close"] if hist is not None and "Close" in hist else pd.Series(dtype="float64")
    price = _num(info.get("currentPrice")) or (float(closes.iloc[-1]) if len(closes) else None)
    short = _num(info.get("shortPercentOfFloat"))
    growth = _num(info.get("revenueGrowth"))
    volume = (
        hist["Volume"].tail(63).mean()
        if hist is not None and "Volume" in hist and len(hist)
        else None
    )
    row = {
        "Ticker": ticker,
        "Price": price,
        "Avg Volume (Shares)": _num(volume),
        "HV 30d": realized_vol_30d(closes),
        "IV Rank (1y)": hv_rank(closes),
        "ATR": atr_14(hist),
        "Next Earnings Date": next_earnings(calendar),
        "Short Interest %": None if short is None else short * 100,
        "Revenue Growth (YoY)": None if growth is None else growth * 100,
        "Debt/Equity": _num(info.get("debtToEquity")),
        "Quality Score (1-5)": None,
        "Sector": info.get("sector") or None,
        "Market Cap": _num(info.get("marketCap")),
        "Beta": _num(info.get("beta")),
        "Trend (Above/Below 20/50/200 EMA)": trend_label(closes),
    }
    row.update(options)
    return row


def fetch_row(ticker: str, today: date | None = None) -> dict:
    """Fetch everything for one ticker from yfinance (network)."""
    today = today or date.today()
    t = yf.Ticker(ticker)
    info = t.info or {}
    hist = t.history(period="1y")
    options: dict = {}
    try:
        expiry = _pick_expiry(list(t.options), today, IV_TARGET_DAYS)
        if expiry:
            chain = t.option_chain(expiry)
            spot = _num(info.get("currentPrice")) or (
                float(hist["Close"].iloc[-1]) if len(hist) else None
            )
            options = option_metrics(spot, chain.calls, chain.puts)
    except Exception as exc:  # no options for this symbol, or a Yahoo hiccup: leave the gaps
        print(f"[INFO] no option data for {ticker}: {exc}")
    try:
        calendar = t.calendar
    except Exception:
        calendar = None
    return build_row(ticker, info, hist, options, calendar)


def fetch_metrics(tickers: list[str]) -> pd.DataFrame:
    """One row per ticker; a ticker that fails entirely is skipped and reported."""
    rows = []
    for ticker in tickers:
        try:
            rows.append(fetch_row(ticker))
        except Exception as exc:
            print(f"[WARNING] yfinance failed for {ticker}: {exc}")
    return pd.DataFrame(rows)
