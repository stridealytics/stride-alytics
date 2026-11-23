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


def test_strategy_tag_reads_live_above_below_trend() -> None:
    from app.screener.weekly_watchlist import _compute_strategy_tag as tag

    def row(iv, trend):
        return {"IV Rank (1y)": iv, "Trend (Above/Below 20/50/200 EMA)": trend}

    assert tag(row(60, "Above 20 / Above 50 / Above 200")) == "Short Put / Bull Put Spread"
    assert tag(row(60, "Below 20 / Below 50")) == "Bear Call Spread / Iron Condor"
    assert tag(row(60, "Above 20 / Below 50")) == "Iron Condor / Short Strangle"
    assert tag(row(60, "Above 20, 50, 200 (Bullish)")) == "Short Put / Bull Put Spread"


def test_strategy_tag_survives_missing_iv_rank_and_trend() -> None:
    from app.screener.weekly_watchlist import _compute_strategy_tag as tag

    assert tag({"IV Rank (1y)": None, "Trend (Above/Below 20/50/200 EMA)": None}) == "Directional Spread"
    assert tag({"IV Rank (1y)": float("nan")}) == "Directional Spread"
    assert tag({"IV Rank (1y)": 60, "Trend (Above/Below 20/50/200 EMA)": None}) == "Iron Condor / Short Strangle"


def test_too_many_failed_tickers_raises(monkeypatch) -> None:
    import pytest

    monkeypatch.delenv("INGEST_MAX_FAIL_PCT", raising=False)
    ingest.check_fetch_rate(80, 100)  # exactly at the limit is fine
    with pytest.raises(RuntimeError, match="too incomplete"):
        ingest.check_fetch_rate(79, 100)
    ingest.check_fetch_rate(0, 0)


def test_stored_universe_is_capped_with_fresh_names_first(monkeypatch) -> None:
    monkeypatch.setenv("INGEST_MAX_TICKERS", "3")
    assert ingest.cap_universe(["A", "B"], ["A", "B"]) == ["A", "B"]  # within the cap: unchanged
    # a partial scrape added extras (X, Y); fresh names keep their place, extras fill the rest
    assert ingest.cap_universe(["A", "B", "C", "X", "Y"], ["C", "A"]) == ["C", "A", "B"]
    assert ingest.cap_universe(["X", "Y", "Z", "W"], []) == ["W", "X", "Y"]  # fetch failed


def test_an_empty_index_list_raises_an_alert(monkeypatch) -> None:
    from app.data_sources import ticker_universe as tu

    alerts = []
    monkeypatch.setattr("app.utils.notify.send_alert", lambda m: alerts.append(m) or True)
    monkeypatch.setattr(tu, "get_sp500_tickers", lambda: [])
    monkeypatch.setattr(tu, "get_nasdaq100_tickers", lambda: ["NDX1", "NDX2"])
    out = tu.load_tickers(use_most_active=False, use_custom=False, max_total=10)
    assert out == ["NDX1", "NDX2"] and len(alerts) == 1 and "SP500" in alerts[0]


def test_unknown_earnings_are_counted_not_silent(capsys) -> None:
    from app.screener.weekly_watchlist import weekly_watchlist

    df = pd.DataFrame(
        {
            "Ticker": ["A"], "Option Score": [8], "Next Earnings Date": [pd.NaT], "Sector": ["T"],
            "Price": [10.0], "IV Rank (1y)": [50.0], "IV 30d": [0.3],
            "Trend (Above/Below 20/50/200 EMA)": ["Above 20"],
        }
    )  # fmt: skip
    assert weekly_watchlist(df).empty
    assert "earnings date unknown" in capsys.readouterr().out


def test_main_survives_characters_the_console_cannot_encode(monkeypatch, capsys) -> None:
    """Regression: emoji prints crashed the live fetch on Windows (cp1252) with a 'charmap' error."""
    import io
    import sys

    from app import main

    raw = io.BytesIO()
    cp1252 = io.TextIOWrapper(raw, encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", cp1252)
    monkeypatch.setattr(main, "run_system", lambda: print("added \U0001f4e5 tickers"))
    assert main.main([]) == 0
    cp1252.flush()
    assert b"added" in raw.getvalue()


def test_index_table_is_parsed_without_lxml() -> None:
    """Regression: pandas.read_html needs lxml, which was never installed, so no ticker loaded."""
    from app.data_sources.ticker_universe import table_column

    html = (
        '<table id="constituents"><tr><th>Symbol</th><th>Security</th></tr>'
        '<tr><td><a>AAPL</a></td><td>Apple</td></tr>'
        "<tr><td>BRK.B</td><td>Berkshire</td></tr><tr><td></td><td>blank</td></tr></table>"
    )
    assert table_column(html, "Symbol") == ["AAPL", "BRK.B"]
    assert table_column(html, "Ticker") == []  # no such column
    assert table_column("<p>no table</p>", "Symbol") == []


def test_live_ingest_returns_real_dates_the_watchlist_can_compare(monkeypatch) -> None:
    """Regression: text earnings dates crashed weekly_watchlist ('>' between str and Timestamp)."""
    from app.screener.weekly_watchlist import weekly_watchlist

    raw = pd.DataFrame(
        {
            "Ticker": ["A", "B"], "Next Earnings Date": ["2099-01-01", None], "Option Score": [8, 8],
            "Sector": ["T", "T"], "Price": [10.0, 10.0], "IV Rank (1y)": [50.0, 50.0],
            "IV 30d": [0.3, 0.3], "Trend (Above/Below 20/50/200 EMA)": ["Above 20", "Above 20"],
        }
    )  # fmt: skip
    monkeypatch.setattr(ingest, "fetch_metrics", lambda t: raw.copy())
    df = ingest.run_ingestion_pipeline(["A", "B"])
    assert pd.api.types.is_datetime64_any_dtype(df["Next Earnings Date"])
    assert list(weekly_watchlist(df)["Ticker"]) == ["A"]  # B has no earnings date: left off


def test_live_mode_refuses_a_stale_csv_but_local_mode_only_warns(monkeypatch, tmp_path) -> None:
    import os
    import time

    import pytest

    from app import main

    csv = tmp_path / "raw_screener.csv"
    csv.write_text("Ticker\nAAA\n")
    old = time.time() - 30 * 86400
    os.utime(csv, (old, old))
    stale = pd.DataFrame({"Ticker": ["AAA"]})
    stale.attrs["source_path"] = str(csv)
    monkeypatch.setattr(main, "load_from_supabase", lambda: pd.DataFrame())
    monkeypatch.setattr(main, "load_local_csv", lambda: stale)

    def boom():
        raise RuntimeError("yahoo down")

    monkeypatch.setattr(ingest, "run_ingestion_pipeline", boom)
    monkeypatch.setenv("INGEST_LIVE", "1")
    with pytest.raises(main.NoDataError, match="refusing to store"):
        main._load_data(False)

    monkeypatch.delenv("INGEST_LIVE")  # local CSV workflow: unchanged, warns only
    assert main._load_data(False)[0] == "csv"
