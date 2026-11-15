"""Free (yfinance) metrics: every calculation on made-up data, no network."""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

from app import ingest
from app.data_sources import free_metrics as fm


def _hist(n: int = 260, drift: float = 0.0005, vol: float = 0.01) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(drift, vol, n)))
    return pd.DataFrame(
        {"Close": close, "High": close * 1.01, "Low": close * 0.99, "Volume": np.full(n, 1_000_000)}
    )


def test_realized_vol_and_gaps() -> None:
    assert 8 < fm.realized_vol_30d(_hist(60)["Close"]) < 25
    assert fm.realized_vol_30d([100, 101]) is None and fm.realized_vol_30d([]) is None
    assert fm.realized_vol_30d([50.0] * 40) == 0.0


def test_hv_rank_is_a_percentile_and_none_without_history() -> None:
    rank = fm.hv_rank(_hist()["Close"])
    assert rank is not None and 0 <= rank <= 100
    assert fm.hv_rank([100.0] * 300) is None and fm.hv_rank([1, 2, 3]) is None


def test_atr_matches_a_fixed_range() -> None:
    hist = pd.DataFrame({"High": [102.0] * 20, "Low": [98.0] * 20, "Close": [100.0] * 20})
    assert fm.atr_14(hist) == 4.0
    assert fm.atr_14(hist.head(5)) is None


def test_trend_label() -> None:
    up = pd.Series(np.linspace(50, 150, 250))
    assert fm.trend_label(up) == "Above 20 / Above 50 / Above 200"
    assert fm.trend_label(up[::-1].reset_index(drop=True)) == "Below 20 / Below 50 / Below 200"
    assert fm.trend_label([1, 2, 3]) is None


def test_expiry_choice_prefers_about_30_days_and_skips_imminent() -> None:
    today = date(2026, 1, 1)
    assert fm._pick_expiry(["2026-01-03", "2026-01-30", "2026-03-20"], today, 30) == "2026-01-30"
    assert fm._pick_expiry(["2026-01-03"], today, 30) is None
    assert fm._pick_expiry(["bad"], today, 30) is None


def test_option_metrics_known_values() -> None:
    calls = pd.DataFrame(
        {
            "strike": [100, 150],
            "bid": [4.0, 0.0],
            "ask": [4.4, 0.1],
            "volume": [300, 50],
            "openInterest": [900, 10],
            "impliedVolatility": [0.30, 0.0],
        }
    )
    puts = pd.DataFrame(
        {
            "strike": [100],
            "bid": [3.8],
            "ask": [4.2],
            "volume": [float("nan")],
            "openInterest": [1200],
            "impliedVolatility": [0.34],
        }
    )
    out = fm.option_metrics(100.0, calls, puts)
    assert out["Option Volume"] == 350 and out["Max OI (Near Exp)"] == 1200
    assert round(out["IV 30d"], 2) == 0.32  # only the two ATM quotes count
    assert round(out["Bid-Ask Spread %"], 2) == 9.76  # median of 9.52% (call) and 10.0% (put)


def test_option_metrics_empty_or_unquoted() -> None:
    assert fm.option_metrics(100.0, pd.DataFrame(), pd.DataFrame()) == {}
    calls = pd.DataFrame(
        {
            "strike": [100],
            "bid": [0.0],
            "ask": [0.0],
            "volume": [None],
            "openInterest": [None],
            "impliedVolatility": [0.0],
        }
    )
    out = fm.option_metrics(100.0, calls, pd.DataFrame())
    assert "Bid-Ask Spread %" not in out and "IV 30d" not in out and "Option Volume" not in out


def test_next_earnings_uses_first_future_date() -> None:
    future = pd.Timestamp.today() + pd.Timedelta(days=20)
    cal = {"Earnings Date": [pd.Timestamp("2020-01-01"), future]}
    assert fm.next_earnings(cal) == future.date().isoformat()
    assert fm.next_earnings({}) is None and fm.next_earnings(None) is None


def test_build_row_never_invents_values() -> None:
    row = fm.build_row(
        "AAA", {"currentPrice": 100, "shortPercentOfFloat": 0.05, "sector": "Tech"}, _hist(), {}
    )
    assert row["Ticker"] == "AAA" and row["Price"] == 100 and row["Short Interest %"] == 5.0
    assert row["Quality Score (1-5)"] is None and "Option Volume" not in row
    bare = fm.build_row("BBB", {}, pd.DataFrame(), {})
    assert bare["Price"] is None and bare["ATR"] is None and bare["HV 30d"] is None
    json.dumps(bare, default=str)


def test_a_failing_ticker_is_skipped(monkeypatch) -> None:
    def fake(ticker, today=None):
        if ticker == "BAD":
            raise RuntimeError("boom")
        return {"Ticker": ticker}

    monkeypatch.setattr(fm, "fetch_row", fake)
    monkeypatch.setattr(fm, "RETRY_DELAYS_SECONDS", ())  # no real sleeping in tests
    assert list(fm.fetch_metrics(["A", "BAD", "B"])["Ticker"]) == ["A", "B"]
    assert fm.fetch_metrics(["BAD"]).empty


def test_a_flaky_ticker_succeeds_on_retry(monkeypatch) -> None:
    calls = {"n": 0}

    def flaky(ticker, today=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("rate limited")
        return {"Ticker": ticker}

    monkeypatch.setattr(fm, "fetch_row", flaky)
    assert fm.fetch_row_with_retry("A", sleep=lambda s: None) == {"Ticker": "A"}
    assert calls["n"] == 3


def test_pipeline_uses_given_tickers(monkeypatch) -> None:
    monkeypatch.setattr(ingest, "fetch_metrics", lambda t: pd.DataFrame({"Ticker": t}))
    assert list(ingest.run_ingestion_pipeline(["X", "Y"])["Ticker"]) == ["X", "Y"]


def test_universe_default_is_free_tier_sized() -> None:
    assert ingest.DEFAULT_MAX_TICKERS <= 200


def test_main_uses_live_data_only_when_enabled_and_falls_back_on_failure(monkeypatch) -> None:
    from app import main

    monkeypatch.setattr(main, "load_from_supabase", lambda: pd.DataFrame({"Ticker": ["DB"]}))
    monkeypatch.delenv("INGEST_LIVE", raising=False)
    assert main._load_data(False)[0] == "supabase"

    monkeypatch.setenv("INGEST_LIVE", "1")
    monkeypatch.setattr(ingest, "run_ingestion_pipeline", lambda: pd.DataFrame({"Ticker": ["L"]}))
    assert main._load_data(False)[0] == "live"

    def boom():
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(ingest, "run_ingestion_pipeline", boom)
    assert main._load_data(False)[0] == "supabase"  # falls back instead of failing the run
