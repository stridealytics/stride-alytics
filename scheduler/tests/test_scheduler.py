"""Smoke tests for the scheduler scripts: no network, no Supabase."""

import importlib
import os
import sys
from datetime import date, datetime, timezone

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS)


def test_every_script_imports_with_scheduler_dependencies_only():
    """Regression: three scripts crashed on import because scipy/structlog were not installed."""
    for name in (
        "calculate_greeks",
        "fetch_market_data",
        "generate_picks",
        "generate_regime",
        "health_check",
        "prune_data",
    ):
        importlib.import_module(name)
    # the backend modules the scheduler reuses must import too
    import app.services.greeks  # noqa: F401
    import app.services.screener  # noqa: F401


def test_greeks_use_the_underlying_spot():
    import calculate_greeks as cg

    rows = [
        {"symbol": "AAA", "strike": 100, "expiry": "2030-01-18", "option_type": "call", "implied_vol": 0.3},
        {"symbol": "AAA", "strike": 100, "expiry": "2030-01-18", "option_type": "put", "implied_vol": None},
        {"symbol": "AAA", "strike": 100, "expiry": "2020-01-17", "option_type": "call", "implied_vol": 0.3},
    ]
    updates = cg.compute_updates(rows, spot=100.0, today=date(2029, 12, 1))
    assert len(updates) == 1  # no IV -> skipped; expired -> skipped
    assert 0.4 < updates[0]["delta"] < 0.7  # ATM call
    assert set(updates[0]) >= {"symbol", "strike", "expiry", "option_type", "delta", "vega"}


def test_prune_plan_never_touches_user_data():
    import prune_data as pd

    plan = pd.plan(date(2026, 6, 1), datetime(2026, 6, 1, tzinfo=timezone.utc))
    tables = {t for t, _, _ in plan}
    assert "options" in tables and "daily_metrics" in tables
    assert not tables & {"trades", "portfolios", "audit_events", "signal_log", "ticker_universe", "alpha_state"}
    assert all(flt.startswith("lt.") for _, _, flt in plan)


def test_picks_are_alphas_list_not_a_second_rule_set():
    import generate_picks as gp

    rows = [
        {"ticker": "aapl", "price": 190.5, "option_score": 8, "iv_rank_1y": 60,
         "strategy": "Short Put / Bull Put Spread", "next_earnings_date": "2027-01-20T00:00:00"},
        {"ticker": "TSLA", "price": 250, "option_score": 6, "iv_rank_1y": 70,
         "strategy": "Bear Call Spread / Iron Condor"},
        {"ticker": "MSFT", "price": 330, "option_score": 9, "iv_rank_1y": 40,
         "strategy": "Iron Condor / Short Strangle"},
        {"ticker": "NOPRICE", "price": None, "option_score": 9},
    ]
    picks = gp.build_picks(rows, "2026-11-23", limit=3)
    assert [p["symbol"] for p in picks] == ["MSFT", "AAPL", "TSLA"]
    assert [p["side"] for p in picks] == ["stock", "put", "call"]  # option type, not direction
    assert picks[0]["confidence"] == 1.0 and picks[1]["confidence"] == 0.89
    assert picks[0]["strike"] is None and picks[0]["expiry"] is None  # never invented
    assert "next earnings 2027-01-20" in picks[1]["rationale"]
    assert all(p["week_of"] == "2026-11-23" for p in picks)


def test_picks_carry_the_company_name_when_known():
    import generate_picks as gp

    rows = [
        {"ticker": "aapl", "price": 190.5, "option_score": 8},
        {"ticker": "AVGO", "price": 900, "option_score": 7},
    ]
    picks = gp.build_picks(rows, "2026-11-23", names={"AAPL": "Apple Inc."})
    assert {p["symbol"]: p["company_name"] for p in picks} == {"AAPL": "Apple Inc.", "AVGO": None}


def test_a_failed_name_lookup_never_blocks_publishing(monkeypatch):
    import types
    import generate_picks as gp

    class Ticker:
        def __init__(self, symbol):
            self.symbol = symbol

        @property
        def info(self):
            if self.symbol == "BAD":
                raise RuntimeError("rate limited")
            return {"longName": "Apple Inc.", "shortName": "Apple"}

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(Ticker=Ticker))
    assert gp.lookup_company_names(["AAPL", "BAD"]) == {"AAPL": "Apple Inc."}


def test_side_follows_the_option_type_in_the_strategy_tag():
    import generate_picks as gp

    expected = {
        "Short Put / Bull Put Spread": "put",
        "Bear Call Spread / Iron Condor": "call",
        "Bull Call Debit Spread / Call Calendar": "call",
        "Bear Put Debit Spread / Put Calendar": "put",
        "Iron Condor / Short Strangle": "stock",
        "Iron Condor / Butterfly": "stock",
        "Directional Spread": "stock",
        None: "stock",
    }
    assert {tag: gp.side_for(tag) for tag in expected} == expected


def test_stale_alpha_list_is_not_published():
    import pytest
    import generate_picks as gp

    gp.check_fresh("2026-11-20", date(2026, 11, 22))  # Friday's list on Sunday is fine
    with pytest.raises(RuntimeError, match="stale"):
        gp.check_fresh("2026-11-01", date(2026, 11, 22))


def test_prune_refuses_tiny_retention(monkeypatch):
    import prune_data

    assert prune_data.retention_errors() == []
    monkeypatch.setattr(prune_data, "ALPHA_DAYS", 0)
    assert prune_data.retention_errors() == ["ALPHA_RETENTION_DAYS=0"]


def test_health_check_expects_the_previous_weekday():
    import health_check

    assert health_check.expected_latest_day(date(2026, 11, 24)) == date(2026, 11, 23)  # Tue -> Mon
    assert health_check.expected_latest_day(date(2026, 11, 23)) == date(2026, 11, 20)  # Mon -> Fri
    assert health_check.expected_latest_day(date(2026, 11, 22)) == date(2026, 11, 20)  # Sun -> Fri
