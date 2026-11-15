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
