"""BR-013 (correlation with an open position) and the entry EV stored on trades (FR-920)."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.domain import ev
from app.domain import thresholds as th
from app.domain.correlation import correlations_with_held, pearson
from app.domain.gate import SymbolData, evaluate_symbol

ALICE = {"Authorization": "Bearer dev:alice"}
TODAY = date.today().isoformat()
WAVE = [math.sin(i / 3) / 100 for i in range(60)]


# ------------------------------------------------------------------ pure correlation


def test_pearson_of_identical_opposite_and_unrelated_series() -> None:
    assert pearson(WAVE, WAVE) == 1.0
    assert pearson(WAVE, [-x for x in WAVE]) == -1.0
    assert abs(pearson(WAVE, [math.cos(i / 3) / 100 for i in range(60)]) or 0) < 0.3


def test_pearson_needs_enough_data_and_a_moving_series() -> None:
    assert pearson(WAVE[:10], WAVE[:10]) is None
    assert pearson(WAVE, [0.01] * 60) is None


def test_pearson_uses_the_latest_shared_days() -> None:
    assert pearson([9.0, 9.0, *WAVE], WAVE) == 1.0


def test_held_correlations_skip_the_candidate_and_flag_missing_data() -> None:
    series = {"A": WAVE, "B": WAVE, "C": None}
    out = correlations_with_held("A", series, ["A", "B", "C", "B"])
    assert out == {"B": 1.0, "C": None}


# ------------------------------------------------------------------ the gate rule


def _symbol_gate(correlations, limits=th.DEFAULTS):
    data = SymbolData(
        symbol="NVDA",
        fetched=True,
        quote_type="EQUITY",
        market_cap=500e9,
        next_earnings=date.today() + timedelta(days=45),
        spread_pct=2.0,
        open_interest=5000,
    )
    return evaluate_symbol(
        data,
        trade_type="put",
        layer="growth",
        news_flag=False,
        today=date.today(),
        limits=limits,
        correlations=correlations,
    )


def test_gate_blocks_a_candidate_above_the_limit_and_allows_it_below() -> None:
    assert [r.rule_id for r in _symbol_gate({"AMD": 0.9}).reasons] == ["BR-013"]
    assert _symbol_gate({"AMD": 0.85}).clear  # the limit itself is allowed
    assert _symbol_gate({"AMD": 0.6}).clear


def test_gate_blocks_when_a_correlation_cannot_be_computed() -> None:
    reason = _symbol_gate({"AMD": None}).reasons[0]
    assert reason.rule_id == "BR-013" and reason.kind == "data"


def test_nothing_held_means_nothing_to_correlate_with() -> None:
    r = _symbol_gate({})
    assert r.clear and "BR-013" in r.checked
    assert "BR-013" not in _symbol_gate(None).checked  # skipped when not supplied


def test_the_limit_is_a_user_setting() -> None:
    assert not _symbol_gate({"AMD": 0.7}, th.resolve({"correlation_max": 0.6})).clear
    assert _symbol_gate({"AMD": 0.9}, th.resolve({"correlation_max": 0.95})).clear
    assert th.loosened({"correlation_max": 0.95}) == ["correlation_max"]
    assert th.loosened({"correlation_max": 0.7}) == []


# ------------------------------------------------------------------ through the API


def _portfolio(client: TestClient) -> str:
    return client.post("/api/v1/portfolio", headers=ALICE, json={"name": "P"}).json()[
        "portfolio_id"
    ]


def _entry(pid: str, symbol: str, **over) -> dict:
    body = {
        "portfolio_id": pid,
        "symbol": symbol,
        "trade_type": "put",
        "direction": "short",
        "entry_price": 2.0,
        "quantity": 1,
        "entry_date": TODAY,
        "strike": 190,
        "expiry": (date.today() + timedelta(days=40)).isoformat(),
        "layer": "base",
    }
    body.update(over)
    return body


def _post(client, pid, symbol, **over):
    return client.post("/api/v1/trades", headers=ALICE, json=_entry(pid, symbol, **over))


def test_a_correlated_second_position_is_refused(client: TestClient, returns_data) -> None:
    pid = _portfolio(client)
    returns_data.by_symbol.update({"NVDA": WAVE, "AMD": WAVE})
    assert _post(client, pid, "NVDA").status_code == 201
    r = _post(client, pid, "AMD")
    assert r.status_code == 409
    reasons = r.json()["error"]["details"]["reasons"]
    assert [x["rule_id"] for x in reasons] == ["BR-013"] and "NVDA" in reasons[0]["message"]


def test_an_unrelated_second_position_is_allowed(client: TestClient) -> None:
    pid = _portfolio(client)
    assert _post(client, pid, "NVDA").status_code == 201
    assert _post(client, pid, "XOM").status_code == 201


def test_adding_to_the_same_symbol_is_not_a_correlation_block(
    client: TestClient, returns_data
) -> None:
    pid = _portfolio(client)
    assert _post(client, pid, "NVDA").status_code == 201
    returns_data.missing.add("NVDA")  # history is down, but the only held symbol is NVDA itself
    assert _post(client, pid, "NVDA").status_code == 201


def test_missing_history_blocks_fail_safe(client: TestClient, returns_data) -> None:
    pid = _portfolio(client)
    assert _post(client, pid, "NVDA").status_code == 201
    returns_data.missing.add("NVDA")
    r = _post(client, pid, "XOM")
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reasons"][0]["kind"] == "data"


def test_the_dry_run_reports_the_correlation_rule(client: TestClient, returns_data) -> None:
    pid = _portfolio(client)
    returns_data.by_symbol.update({"NVDA": WAVE, "AMD": WAVE})
    _post(client, pid, "NVDA")
    body = {"symbol": "AMD", "trade_type": "put", "layer": "base"}
    data = client.post("/api/v1/gate/check", headers=ALICE, json=body).json()["data"]
    assert data["clear"] is False and "BR-013" in data["checked"]
    assert "BR-013" not in data["not_evaluated"]


def test_a_user_can_loosen_the_correlation_limit(client: TestClient, returns_data) -> None:
    pid = _portfolio(client)
    returns_data.by_symbol.update({"NVDA": WAVE, "AMD": WAVE})
    _post(client, pid, "NVDA")
    r = client.put(
        "/api/v1/settings", headers=ALICE, json={"thresholds": {"correlation_max": 0.99}}
    )
    assert r.json()["warnings"] == ["correlation_max"]
    assert _post(client, pid, "AMD").status_code == 409  # a perfect 1.0 is still above 0.99


# ------------------------------------------------------------------ entry EV


def test_entry_ev_for_a_short_option() -> None:
    # PoP 0.85 (delta 0.15), keeps $200, risks $1,000: 0.85*200 - 0.15*1000 = 20
    assert (
        ev.entry_ev(
            trade_type="put",
            direction="short",
            quantity=1,
            credit=2.0,
            risk_amount=1000,
            delta=-0.15,
        )
        == 20.0
    )


@pytest.mark.parametrize(
    "over",
    [
        {"trade_type": "stock"},
        {"direction": "long"},
        {"credit": None},
        {"risk_amount": None},
        {"delta": None},
    ],
)
def test_entry_ev_is_not_scored_without_its_inputs(over) -> None:
    args = dict(
        trade_type="put", direction="short", quantity=1, credit=2.0, risk_amount=1000, delta=-0.15
    )
    args.update(over)
    assert ev.entry_ev(**args) is None


def test_a_scored_trade_stores_its_ev_and_the_calibration_report_uses_it(
    client: TestClient,
) -> None:
    pid = _portfolio(client)
    r = _post(client, pid, "NVDA", credit=2.0, risk_amount=1000, band="B")
    assert r.status_code == 201
    # the fake feed's delta is -0.15 for a put: PoP 0.85
    assert r.json()["entry_ev"] == 20.0
    tid = r.json()["trade_id"]
    client.post(
        f"/api/v1/trades/{tid}/close", headers=ALICE, json={"exit_price": 0.5, "exit_date": TODAY}
    )
    data = client.get("/api/v1/analytics/ev-calibration", headers=ALICE).json()["data"]
    group = data["groups"][0]
    assert group["avg_expected"] == 20.0 and group["with_expected"] == 1
    assert group["avg_pnl"] == 150.0


def test_unscored_trades_have_no_entry_ev_and_still_count_as_realised(
    client: TestClient,
) -> None:
    pid = _portfolio(client)
    r = _post(client, pid, "NVDA")  # no credit or risk amount
    assert r.json()["entry_ev"] is None
    client.post(
        f"/api/v1/trades/{r.json()['trade_id']}/close",
        headers=ALICE,
        json={"exit_price": 1.0, "exit_date": TODAY},
    )
    group = client.get("/api/v1/analytics/ev-calibration", headers=ALICE).json()["data"]["groups"][
        0
    ]
    assert group["trades"] == 1 and group["avg_expected"] is None and group["with_expected"] == 0


def test_a_backdated_entry_is_not_scored(client: TestClient) -> None:
    pid = _portfolio(client)
    old = (date.today() - timedelta(days=30)).isoformat()
    r = _post(client, pid, "NVDA", entry_date=old, credit=2.0, risk_amount=1000)
    assert r.status_code == 201 and r.json()["entry_ev"] is None
