"""Dry run (read and report, write nothing) and the checks that tie a run to one Supabase project."""

from __future__ import annotations

import os

import pandas as pd

from app import ingest, inspect_target
from app import main as alpha_main
from app.database import insert_daily, universe
from app.preflight import check_environment
from tests.fake_supabase import FakeSupabase


def _df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Ticker": ["AAPL", "MSFT"],
            "Price": [1.0, 2.0],
            "Option Score": [8, 6],
            "Band": ["A", "B"],
        }
    )


def test_a_dry_run_reads_and_reports_but_writes_nothing(monkeypatch) -> None:
    db = FakeSupabase()
    monkeypatch.setattr(insert_daily, "get_supabase_client", lambda: db)
    monkeypatch.setattr("app.database.universe._client", lambda: db)
    monkeypatch.setenv("ALPHA_DRY_RUN", "1")
    report = insert_daily.sync_day(_df(), _df(), day="2026-12-01")
    assert report["daily_metrics"]["inserted"] == 2  # what WOULD be written
    assert universe.sync_universe(["A", "B"], client=db).add == ["A", "B"]
    alpha_main._after_load(_df())  # sets no sectors and no protection flag
    assert db.log == []
    assert not any(db.tables.get(t) for t in db.tables)


def test_a_dry_run_ingest_uses_the_planned_universe_without_storing_it(monkeypatch) -> None:
    db = FakeSupabase()
    monkeypatch.setattr("app.database.universe._client", lambda: db)
    monkeypatch.setenv("ALPHA_DRY_RUN", "1")
    assert ingest.resolve_universe(["A", "B"]) == ["A", "B"]
    assert db.log == []


def test_main_dry_run_flag_sets_the_mode(monkeypatch) -> None:
    monkeypatch.setenv("ALPHA_DRY_RUN", "0")  # registered, so it is removed again afterwards
    monkeypatch.setattr(alpha_main, "run_system", lambda: None)
    assert alpha_main.main(["--dry-run"]) == 0
    assert os.environ["ALPHA_DRY_RUN"] == "1"


def test_the_run_refuses_a_different_project_than_the_one_named() -> None:
    env = {
        "SUPABASE_URL": "https://realproj.supabase.co",
        "SUPABASE_KEY": "k",
        "ALPHA_EXPECT_PROJECT": "testproj",
    }
    bad = check_environment(env, have_service_file=False)
    assert not bad.ok and "ALPHA_EXPECT_PROJECT" in bad.errors[0]
    good = check_environment({**env, "ALPHA_EXPECT_PROJECT": "realproj"}, have_service_file=False)
    assert good.ok


def test_inspect_reports_project_counts_and_protection_without_writing(monkeypatch) -> None:
    monkeypatch.delenv("ALPHA_EXPECT_PROJECT", raising=False)
    db = FakeSupabase(strict=True)
    db.tables["daily_metrics"] = [
        {"date": "2026-12-01", "ticker": "A"},
        {"date": "2026-12-02", "ticker": "A"},
    ]
    db.tables["alpha_state"] = [{"key": "initial_load_complete", "value": "true"}]
    text = "\n".join(inspect_target.inspect(db, "https://abcd1234.supabase.co"))
    assert "Supabase project: abcd1234" in text
    assert "2 rows" in text
    assert "ticker_universe" in text and "missing" in text
    assert "Newest daily_metrics day: 2026-12-02" in text
    assert "protected (initial load complete): yes" in text
    assert db.log == []


def test_project_ref_handles_odd_urls() -> None:
    assert inspect_target.project_ref("https://abcd1234.supabase.co") == "abcd1234"
    assert inspect_target.project_ref("http://localhost:54321") == "localhost"
    assert inspect_target.project_ref(None).startswith("(SUPABASE_URL")
