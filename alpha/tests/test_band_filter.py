"""Band rule: apply_daily_filters drops band D and E rows."""

import pandas as pd

from app.screener.apply_filters import apply_daily_filters


def _row(ticker: str, band: str) -> dict:
    return {
        "Ticker": ticker,
        "Band": band,
        "Option Volume": 5000,
        "Max OI (Near Exp)": 1000,
        "Bid-Ask Spread %": 2,
        "Next Earnings Date": pd.Timestamp.today() + pd.Timedelta(days=60),
        "Short Interest %": 3,
        "IV Rank (1y)": 60,
        "IV 30d": 30,
        "HV 30d": 25,
    }


def test_only_bands_a_b_c_survive() -> None:
    df = pd.DataFrame([_row(f"T{b}", b) for b in "ABCDE"])
    out = apply_daily_filters(df)
    assert list(out["Band"]) == ["A", "B", "C"]
