"""Ticker universe (loaded once, then only differences) and the protection against wiping data."""

from __future__ import annotations

import pandas as pd
import pytest

from app import ingest
from app import main as alpha_main
from app.database import insert_daily, safety, universe
from tests.fake_supabase import FakeSupabase


def _tickers(n: int, prefix: str = "T") -> list[str]:
    return [f"{prefix}{i:03d}" for i in range(n)]


# ------------------------------------------------------------------ the plan (pure)


def test_clean_uppercases_trims_dedupes_and_drops_blanks() -> None:
    assert universe.clean([" aapl", "AAPL", "", "nan", "msft"]) == ["AAPL", "MSFT"]


def test_plan_adds_new_and_keeps_everything_else_untouched() -> None:
    stored = {"A": {"status": "active"}, "B": {"status": "active"}}
    plan = universe.plan_sync(stored, ["A", "B", "C"])
    assert (plan.add, plan.reactivate, plan.remove) == (["C"], [], [])


def test_plan_soft_removes_and_reactivates() -> None:
    stored = {t: {"status": "active"} for t in _tickers(50)}
    stored["OLD"] = {"status": "removed"}
    fresh = _tickers(50)[1:] + ["OLD"]
    plan = universe.plan_sync(stored, fresh)
    assert plan.remove == ["T000"] and plan.reactivate == ["OLD"] and plan.add == []


def test_an_empty_fresh_list_removes_nothing() -> None:
    plan = universe.plan_sync({"A": {"status": "active"}}, [])
    assert plan.remove == [] and plan.removal_skipped


def test_a_mass_removal_is_held_back_but_additions_still_happen() -> None:
    stored = {t: {"status": "active"} for t in _tickers(100)}
    fresh = _tickers(100)[:40] + ["NEW"]  # 60 would vanish
    plan = universe.plan_sync(stored, fresh)
    assert plan.remove == [] and plan.add == ["NEW"] and "bad fetch" in plan.removal_skipped


def test_a_normal_daily_change_is_applied() -> None:
    stored = {t: {"status": "active"} for t in _tickers(100)}
    fresh = _tickers(100)[3:] + ["NEW1", "NEW2"]  # 3 dropped, 2 added
    plan = universe.plan_sync(stored, fresh)
    assert plan.remove == _tickers(3) and plan.add == ["NEW1", "NEW2"]


# ------------------------------------------------------------------ applying it


def test_first_sync_is_the_bulk_load_and_the_second_writes_nothing() -> None:
    db = FakeSupabase()
    first = universe.sync_universe(_tickers(10), client=db)
    assert len(first.add) == 10 and len(db.tables["ticker_universe"]) == 10
    db.log.clear()
    second = universe.sync_universe(_tickers(10), client=db)
    assert second.changes == 0 and db.log == []


def test_each_ticker_is_stored_once_even_if_listed_twice() -> None:
    db = FakeSupabase()
    universe.sync_universe(["A", "a", "B", "A"], client=db)
    assert sorted(r["ticker"] for r in db.tables["ticker_universe"]) == ["A", "B"]


def test_daily_sync_writes_only_the_difference_and_never_deletes() -> None:
    db = FakeSupabase()
    universe.sync_universe(_tickers(100), client=db)
    original = {r["ticker"]: dict(r) for r in db.tables["ticker_universe"]}
    db.log.clear()
    universe.sync_universe(_tickers(100)[2:] + ["NEW"], client=db)
    assert db.ops("delete") == []
    assert db.ops("insert") == [("insert", "ticker_universe", 1)]
    rows = {r["ticker"]: r for r in db.tables["ticker_universe"]}
    assert rows["T000"]["status"] == "removed" and rows["T001"]["removed_at"]
    assert rows["NEW"]["status"] == "active" and len(rows) == 101  # history kept
    assert rows["T050"] == original["T050"]  # untouched rows are byte-identical


def test_a_returning_ticker_is_reactivated() -> None:
    db = FakeSupabase()
    universe.sync_universe(_tickers(100), client=db)
    universe.sync_universe(_tickers(100)[1:], client=db)
    universe.sync_universe(_tickers(100), client=db)
    row = next(r for r in db.tables["ticker_universe"] if r["ticker"] == "T000")
    assert row["status"] == "active" and row["removed_at"] is None


def test_active_tickers_excludes_removed() -> None:
    db = FakeSupabase()
    universe.sync_universe(_tickers(100), client=db)
    universe.sync_universe(_tickers(100)[1:], client=db)
    assert "T000" not in universe.active_tickers(db) and len(universe.active_tickers(db)) == 99


def test_a_sector_is_filled_once_and_never_overwritten() -> None:
    db = FakeSupabase()
    universe.sync_universe(["A", "B"], client=db)
    assert universe.fill_sectors({"A": "Tech", "B": "Energy", "Z": "Other"}, db) == 2
    assert universe.fill_sectors({"A": "Changed"}, db) == 0
    assert {r["ticker"]: r["sector"] for r in db.tables["ticker_universe"]} == {
        "A": "Tech",
        "B": "Energy",
    }


# ------------------------------------------------------------------ ingest uses the stored list


def test_ingest_uses_the_stored_universe_and_falls_back_on_a_failed_fetch(monkeypatch) -> None:
    db = FakeSupabase()
    monkeypatch.setattr("app.database.universe._client", lambda: db)
    assert ingest.resolve_universe(["A", "B", "C"]) == ["A", "B", "C"]
    assert ingest.resolve_universe([]) == ["A", "B", "C"]  # list source down: stored list is used


def test_ingest_still_works_when_the_database_is_unreachable(monkeypatch) -> None:
    def down():
        raise RuntimeError("no database")

    monkeypatch.setattr("app.database.universe._client", down)
    assert ingest.resolve_universe(["A", "B"]) == ["A", "B"]


# ------------------------------------------------------------------ protection against wiping


def test_nothing_is_blocked_before_the_initial_load() -> None:
    db = FakeSupabase()
    safety.require_unlocked("clear", db)  # no flag yet


def test_after_the_initial_load_bulk_deletes_are_refused(monkeypatch) -> None:
    db = FakeSupabase()
    db.tables["daily_metrics"] = [{"date": "2026-12-01", "ticker": "AAPL"}]
    assert safety.mark_loaded(db) is True and safety.mark_loaded(db) is False
    monkeypatch.setattr(insert_daily, "get_supabase_client", lambda: db)
    with pytest.raises(safety.DestructiveOperationBlocked):
        insert_daily.clear_all_tables()
    monkeypatch.setattr("app.database.supabase_client.get_supabase_client", lambda: db)
    from app.database import supabase_client

    with pytest.raises(safety.DestructiveOperationBlocked):
        supabase_client.delete_rows("daily_metrics", "ticker", "AAPL")
    assert len(db.tables["daily_metrics"]) == 1 and db.ops("delete") == []


def test_if_the_flag_cannot_be_read_deletes_are_blocked(monkeypatch) -> None:
    class Broken(FakeSupabase):
        def table(self, name):
            raise RuntimeError("db down")

    with pytest.raises(safety.DestructiveOperationBlocked, match="could not check"):
        safety.require_unlocked("clear", Broken())


def test_the_explicit_override_allows_a_deliberate_reset(monkeypatch) -> None:
    db = FakeSupabase()
    db.tables["daily_metrics"] = [{"date": "2026-12-01", "ticker": "AAPL"}]
    safety.mark_loaded(db)
    monkeypatch.setattr(insert_daily, "get_supabase_client", lambda: db)
    monkeypatch.setenv(safety.UNLOCK_ENV, safety.UNLOCK_VALUE)
    insert_daily.clear_all_tables()
    assert db.tables["daily_metrics"] == []


def test_a_successful_run_stores_sectors_then_protects_the_data(monkeypatch) -> None:
    db = FakeSupabase()
    monkeypatch.setattr("app.database.universe._client", lambda: db)
    monkeypatch.setattr("app.database.safety._client", lambda: db)
    universe.sync_universe(["AAPL", "MSFT"], client=db)
    df = pd.DataFrame({"Ticker": ["AAPL", "MSFT"], "Sector": ["Technology", None]})
    alpha_main._after_load(df)
    rows = {r["ticker"]: r for r in db.tables["ticker_universe"]}
    assert rows["AAPL"]["sector"] == "Technology" and not rows["MSFT"].get("sector")
    assert safety.is_loaded(db)


def test_bookkeeping_failure_is_a_warning_not_a_failed_run(monkeypatch, capsys) -> None:
    def down():
        raise RuntimeError("no table")

    monkeypatch.setattr("app.database.universe._client", down)
    alpha_main._after_load(pd.DataFrame({"Ticker": ["A"], "Sector": ["X"]}))
    assert "WARNING" in capsys.readouterr().out
