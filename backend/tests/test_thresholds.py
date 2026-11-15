"""User-configurable rule thresholds (FR-830): defaults, validation, effect on the rules, API."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain import thresholds as th
from app.domain.alerts import MarketInput, PositionInput, evaluate_position
from app.domain.gate import SymbolData, evaluate_symbol
from app.domain.portfolio_risk import PositionRisk, calculate_portfolio_risk, entry_risk_reason

TODAY = date(2026, 6, 1)
ALICE = {"Authorization": "Bearer dev:alice"}
BOB = {"Authorization": "Bearer dev:bob"}


# ------------------------------------------------------------------ the module


def test_defaults_are_the_documented_values() -> None:
    d = th.DEFAULTS
    assert (d.spread_max_pct, d.open_interest_min, d.market_cap_min, d.earnings_window_days) == (
        10.0,
        500,
        2e9,
        14,
    )
    assert (d.max_capital_at_risk_pct, d.max_sector_risk_pct, d.max_net_delta_pct) == (50, 25, 100)
    assert (d.dte_watch, d.dte_warning, d.delta_assignment) == (7, 3, 0.70)


def test_every_default_is_inside_its_own_bounds() -> None:
    for key, value in th.DEFAULTS.to_dict().items():
        low, high = th.BOUNDS[key]
        assert low <= value <= high, key
    assert set(th.BOUNDS) == set(th.DEFAULTS.to_dict())


@pytest.mark.parametrize(
    "bad",
    [
        {"nope": 1},
        {"spread_max_pct": "10"},
        {"spread_max_pct": True},
        {"spread_max_pct": 0.5},
        {"spread_max_pct": 26},
        {"dte_warning": 9},  # not below the default watch of 7
        {"dte_watch": 2},  # not above the default warning of 3
    ],
)
def test_bad_values_are_rejected(bad) -> None:
    with pytest.raises(ValueError):
        th.validate(bad)


def test_bounds_are_inclusive_and_values_become_floats() -> None:
    assert th.validate({"spread_max_pct": 1, "open_interest_min": 5000}) == {
        "spread_max_pct": 1.0,
        "open_interest_min": 5000.0,
    }


def test_resolve_applies_overrides_and_ignores_junk() -> None:
    t = th.resolve({"spread_max_pct": 15, "open_interest_min": "x", "bogus": 1, "dte_watch": 999})
    assert t.spread_max_pct == 15 and t.open_interest_min == 500 and t.dte_watch == 7
    assert th.resolve(None) == th.DEFAULTS


def test_loosening_is_reported_but_tightening_is_not() -> None:
    assert th.loosened({"spread_max_pct": 15, "open_interest_min": 100}) == [
        "open_interest_min",
        "spread_max_pct",
    ]
    assert th.loosened({"spread_max_pct": 5, "open_interest_min": 900, "dte_watch": 20}) == []


# ------------------------------------------------------------------ effect on the rules


def _data(**over) -> SymbolData:
    base = dict(
        symbol="AAPL",
        fetched=True,
        quote_type="EQUITY",
        market_cap=50e9,
        next_earnings=TODAY + timedelta(days=30),
        spread_pct=3.0,
        open_interest=1000,
    )
    base.update(over)
    return SymbolData(**base)


def _gate(data: SymbolData, limits=th.DEFAULTS):
    return evaluate_symbol(
        data, trade_type="put", layer="growth", news_flag=False, today=TODAY, limits=limits
    )


def test_gate_uses_the_users_limits_at_the_boundary() -> None:
    assert [r.rule_id for r in _gate(_data(spread_pct=12)).reasons] == ["BR-017"]
    assert _gate(_data(spread_pct=12), th.resolve({"spread_max_pct": 12})).clear
    assert not _gate(_data(open_interest=700), th.resolve({"open_interest_min": 800})).clear
    assert _gate(_data(open_interest=450), th.resolve({"open_interest_min": 400})).clear
    assert not _gate(_data(market_cap=3e9), th.resolve({"market_cap_min": 5e9})).clear
    soon = _data(next_earnings=TODAY + timedelta(days=20))
    assert _gate(soon).clear
    assert not _gate(soon, th.resolve({"earnings_window_days": 21})).clear


def test_gate_messages_show_the_users_numbers() -> None:
    reason = _gate(_data(spread_pct=8), th.resolve({"spread_max_pct": 5})).reasons[0]
    assert "5%" in reason.message


def test_portfolio_limits_follow_the_users_values() -> None:
    positions = [PositionRisk(symbol="A", risk_amount=40_000, sector="Tech")]
    assert calculate_portfolio_risk(positions, 100_000).breaches[0].code == "sector"
    loose = th.resolve({"max_sector_risk_pct": 50})
    assert calculate_portfolio_risk(positions, 100_000, loose).breaches == []
    tight = th.resolve({"max_capital_at_risk_pct": 30})
    kinds = {b.code for b in calculate_portfolio_risk(positions, 100_000, tight).breaches}
    assert "total_risk" in kinds
    assert calculate_portfolio_risk(positions, 100_000, tight).limits["capital_at_risk_pct"] == 30
    assert entry_risk_reason(100_000, 40_000, None) is None
    assert entry_risk_reason(100_000, 40_000, None, tight) is not None


def _alert(delta: float, dte: int, limits=th.DEFAULTS):
    pos = PositionInput(
        trade_id="t",
        symbol="AAPL",
        trade_type="put",
        direction="short",
        quantity=1,
        entry_price=2.0,
        strike=100.0,
        expiry=TODAY + timedelta(days=dte),
        layer="base",
    )
    market = MarketInput(available=True, spot=110.0, mark=1.8, delta=delta, theta=0.05)
    return evaluate_position(pos, market, today=TODAY, limits=limits)


def _codes(alert) -> list[str]:
    return [r.code for r in alert.reasons]


def test_alert_timing_and_assignment_delta_follow_the_users_values() -> None:
    assert _alert(-0.2, 10).severity == "normal"
    assert _alert(-0.2, 10, th.resolve({"dte_watch": 14})).severity == "watch"
    assert "assignment_risk" in _codes(_alert(-0.75, 20))
    assert "assignment_risk" not in _codes(_alert(-0.75, 20, th.resolve({"delta_assignment": 0.9})))
    assert _alert(-0.2, 5, th.resolve({"dte_warning": 5, "dte_watch": 10})).severity == "warning"


# ------------------------------------------------------------------ API


def _put(client: TestClient, headers, body):
    return client.put("/api/v1/settings", headers=headers, json=body)


def test_settings_start_with_no_overrides_and_full_effective_values(client: TestClient) -> None:
    data = client.get("/api/v1/settings", headers=ALICE).json()["data"]
    assert data["thresholds"] == {} and data["effective_thresholds"] == th.DEFAULTS.to_dict()


def test_info_endpoint_lists_defaults_bounds_and_current_values(client: TestClient) -> None:
    assert _put(client, ALICE, {"thresholds": {"spread_max_pct": 15}}).status_code == 200
    info = client.get("/api/v1/settings/thresholds", headers=ALICE).json()["data"]
    assert info["defaults"]["spread_max_pct"] == 10
    assert info["bounds"]["spread_max_pct"] == {"min": 1, "max": 25}
    assert info["overrides"] == {"spread_max_pct": 15.0}
    assert info["effective"]["spread_max_pct"] == 15
    assert info["loosened"] == ["spread_max_pct"]


def test_saving_loosened_values_returns_a_warning(client: TestClient) -> None:
    r = _put(client, ALICE, {"thresholds": {"open_interest_min": 100}})
    assert r.status_code == 200 and r.json()["warnings"] == ["open_interest_min"]
    tight = _put(client, ALICE, {"thresholds": {"open_interest_min": 900}})
    assert tight.json()["warnings"] == []


def test_a_change_is_written_to_the_audit_log(client: TestClient) -> None:
    _put(client, ALICE, {"thresholds": {"open_interest_min": 100}})
    body = client.get("/api/v1/logs/audit", headers=ALICE).json()
    rows = body["data"] if isinstance(body, dict) else body
    row = next(x for x in rows if x["action"] == "settings.update")
    assert row["before"] == {"thresholds": {}}
    assert row["after"] == {"thresholds": {"open_interest_min": 100.0}}


def test_invalid_thresholds_are_rejected_and_nothing_changes(client: TestClient) -> None:
    for body in ({"spread_max_pct": 99}, {"unknown": 1}, {"dte_warning": 20}):
        assert _put(client, ALICE, {"thresholds": body}).status_code == 422
    assert client.get("/api/v1/settings", headers=ALICE).json()["data"]["thresholds"] == {}


def test_empty_object_resets_to_defaults_and_users_are_separate(client: TestClient) -> None:
    _put(client, ALICE, {"thresholds": {"spread_max_pct": 15}})
    assert client.get("/api/v1/settings", headers=BOB).json()["data"]["thresholds"] == {}
    _put(client, ALICE, {"thresholds": {}})
    assert client.get("/api/v1/settings", headers=ALICE).json()["data"]["thresholds"] == {}


def test_a_changed_limit_changes_the_portfolio_risk_report(client: TestClient) -> None:
    risk = client.get("/api/v1/portfolio/risk", headers=ALICE).json()["data"]
    assert risk["limits"]["capital_at_risk_pct"] == 50
    _put(client, ALICE, {"thresholds": {"max_capital_at_risk_pct": 30}})
    risk = client.get("/api/v1/portfolio/risk", headers=ALICE).json()["data"]
    assert risk["limits"]["capital_at_risk_pct"] == 30
