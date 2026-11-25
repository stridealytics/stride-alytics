"""Pipeline I/O: date handling, replace-day semantics, data-source policy, failure signalling."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app import main as alpha_main
from app.database import insert_daily
from tests.fake_supabase import FakeSupabase


def _scored_df() -> pd.DataFrame:
    df = pd.DataFrame(
        [
            {
                "Ticker": "AAPL",
                "Price": 190.5,
                "Option Score": 8,
                "Band": "A",
                "Strategy Tag": "Short Put",
                "Trend (Above/Below 20/50/200 EMA)": "Above 20, 50, 200 (Bullish)",
                "Next Earnings Date": pd.NaT,
                "Sector": "Technology",
                "IV Rank (1y)": float("nan"),
            },
            {
                "Ticker": "MSFT",
                "Price": 330.0,
                "Option Score": 6,
                "Band": "B",
                "Strategy Tag": "Iron Condor",
                "Trend (Above/Below 20/50/200 EMA)": "Range",
                "Next Earnings Date": pd.Timestamp("2027-01-05"),
                "Sector": "Technology",
                "IV Rank (1y)": 55.0,
            },
        ]
    )
    return df


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeSupabase:
    client = FakeSupabase()
    monkeypatch.setattr(insert_daily, "get_supabase_client", lambda: client)
    return client


# --- dates ------------------------------------------------------------------


def test_date_is_always_a_plain_day_string() -> None:
    mapped = insert_daily._map_columns(_scored_df())
    assert (mapped["date"] == insert_daily.today_str()).all()
    assert len(mapped["date"].iloc[0]) == 10  # YYYY-MM-DD, no time component


def test_existing_timestamp_dates_are_trimmed_and_day_override_wins() -> None:
    df = _scored_df().assign(date="2026-11-14T10:23:45.123456")
    assert insert_daily._map_columns(df)["date"].iloc[0] == "2026-11-14"
    assert (insert_daily._map_columns(df, day="2026-12-01")["date"] == "2026-12-01").all()


def test_nan_and_nat_become_null_not_strings() -> None:
    out = insert_daily._convert_timestamps(
        [{"a": float("nan"), "b": pd.NaT, "c": pd.Timestamp("2026-01-02"), "d": math.inf, "e": 3}]
    )[0]
    assert out == {"a": None, "b": None, "c": "2026-01-02T00:00:00", "d": None, "e": 3}


# --- sync_day: add and update only what changed ------------------------------


def _weekly(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Option Score"] >= 6].assign(Date=pd.Timestamp("2026-12-01"))


def test_first_write_inserts_everything_and_deletes_nothing(fake_client: FakeSupabase) -> None:
    df = _scored_df()
    report = insert_daily.sync_day(df, _weekly(df), day="2026-12-01")
    assert report["daily_metrics"] == {"inserted": 2, "updated": 0, "unchanged": 0, "removed": 0}
    assert fake_client.ops("delete") == []
    for rows in fake_client.tables.values():
        assert {r["date"] for r in rows} == {"2026-12-01"}


def test_rerunning_with_the_same_data_writes_nothing(fake_client: FakeSupabase) -> None:
    df = _scored_df()
    insert_daily.sync_day(df, _weekly(df), day="2026-12-01")
    fake_client.log.clear()
    report = insert_daily.sync_day(df, _weekly(df), day="2026-12-01")
    assert fake_client.log == []
    assert report["daily_metrics"]["unchanged"] == 2


def test_only_changed_rows_and_columns_are_updated(fake_client: FakeSupabase) -> None:
    df = _scored_df()
    insert_daily.sync_day(df, _weekly(df), day="2026-12-01")
    fake_client.log.clear()
    changed = df.copy()
    changed.loc[changed["Ticker"] == "MSFT", "Price"] = 340.0
    report = insert_daily.sync_day(changed, _weekly(changed), day="2026-12-01")
    assert report["daily_metrics"] == {"inserted": 0, "updated": 1, "unchanged": 1, "removed": 0}
    assert fake_client.ops("insert") == [] and fake_client.ops("delete") == []
    rows = {r["ticker"]: r for r in fake_client.tables["daily_metrics"]}
    assert rows["MSFT"]["price"] == 340.0 and rows["AAPL"]["price"] == 190.5


def test_a_new_ticker_is_added_and_a_missing_one_keeps_its_row(fake_client: FakeSupabase) -> None:
    df = _scored_df()
    insert_daily.sync_day(df, _weekly(df), day="2026-12-01")
    fake_client.log.clear()
    only_msft = df[df["Ticker"] == "MSFT"]
    extra = pd.concat([only_msft, only_msft.assign(Ticker="NVDA")], ignore_index=True)
    report = insert_daily.sync_day(extra, _weekly(extra), day="2026-12-01")
    assert report["daily_metrics"]["inserted"] == 1
    tickers = {r["ticker"] for r in fake_client.tables["daily_metrics"]}
    assert tickers == {"AAPL", "MSFT", "NVDA"}  # AAPL was not deleted


def test_watchlist_drops_only_the_tickers_that_left_it(fake_client: FakeSupabase) -> None:
    df = _scored_df()
    insert_daily.sync_day(df, _weekly(df), day="2026-12-01")  # AAPL (8) and MSFT (6)
    smaller = df.copy()
    smaller.loc[smaller["Ticker"] == "MSFT", "Option Score"] = 2
    report = insert_daily.sync_day(smaller, _weekly(smaller), day="2026-12-01")
    assert report["weekly_watchlist"]["removed"] == 1
    assert {r["ticker"] for r in fake_client.tables["weekly_watchlist"]} == {"AAPL"}
    assert len(fake_client.tables["daily_metrics"]) == 2  # nothing else was removed


def test_an_empty_watchlist_never_empties_the_stored_day(fake_client: FakeSupabase) -> None:
    df = _scored_df()
    insert_daily.sync_day(df, _weekly(df), day="2026-12-01")
    insert_daily.sync_day(df, _weekly(df).iloc[0:0], day="2026-12-01")
    assert len(fake_client.tables["weekly_watchlist"]) == 2


def test_other_days_are_never_touched(fake_client: FakeSupabase) -> None:
    df = _scored_df()
    insert_daily.sync_day(df, _weekly(df), day="2026-11-30")
    insert_daily.sync_day(df.assign(Price=1.0), _weekly(df), day="2026-12-01")
    old = [r for r in fake_client.tables["daily_metrics"] if r["date"] == "2026-11-30"]
    assert len(old) == 2 and {r["price"] for r in old} == {190.5, 330.0}


def test_legacy_timestamped_rows_are_updated_not_duplicated(fake_client: FakeSupabase) -> None:
    df = _scored_df()
    fake_client.tables["daily_metrics"] = [
        {"date": "2026-12-01T10:00:00", "ticker": "AAPL", "price": 1.0},
        {"date": "2026-12-01T10:00:00", "ticker": "MSFT", "price": 330.0},
    ]
    report = insert_daily.sync_day(df, _weekly(df), day="2026-12-01")
    assert report["daily_metrics"]["inserted"] == 0
    assert len(fake_client.tables["daily_metrics"]) == 2


def test_nothing_is_written_if_building_the_payload_fails(
    fake_client: FakeSupabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a, **k):
        raise ValueError("bad data")

    monkeypatch.setattr(insert_daily, "_rows", boom)
    with pytest.raises(ValueError):
        insert_daily.sync_day(_scored_df(), _scored_df(), day="2026-12-01")
    assert fake_client.log == []


def test_supabase_errors_are_raised_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(insert_daily, "get_supabase_client", lambda: FakeSupabase(fail_on="insert"))
    with pytest.raises(RuntimeError, match="simulated"):
        insert_daily.sync_day(_scored_df(), _scored_df(), day="2026-12-01")


# --- data-source policy -----------------------------------------------------


def _no_real_data(monkeypatch: pytest.MonkeyPatch) -> None:
    # config.py loads alpha/.env at import; a developer's ALPHA_EXPECT_PROJECT would otherwise make
    # the pre-flight guard reject these tests' (absent) Supabase URL.
    monkeypatch.delenv("ALPHA_EXPECT_PROJECT", raising=False)
    monkeypatch.setattr(alpha_main, "load_from_supabase", lambda: pd.DataFrame())
    monkeypatch.setattr(alpha_main, "load_local_csv", lambda: pd.DataFrame())


def test_no_data_fails_instead_of_inventing_data(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_real_data(monkeypatch)
    with pytest.raises(alpha_main.NoDataError):
        alpha_main._load_data(allow_sample=False)


def test_sample_data_is_opt_in_and_never_written(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_real_data(monkeypatch)
    source, df = alpha_main._load_data(allow_sample=True)
    assert source == "sample" and not df.empty
    # earnings dates are relative to today, so the demo never "expires"
    assert (df["Next Earnings Date"] > pd.Timestamp.today()).all()

    def must_not_write(*a, **k):
        raise AssertionError("sample data must not be written to Supabase")

    monkeypatch.setattr(alpha_main, "sync_day", must_not_write)
    alpha_main.run_system(allow_sample=True)  # completes without writing


def test_supabase_data_is_preferred_over_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alpha_main, "load_from_supabase", lambda: _scored_df())
    monkeypatch.setattr(
        alpha_main, "load_local_csv", lambda: (_ for _ in ()).throw(AssertionError("unused"))
    )
    source, _ = alpha_main._load_data(allow_sample=False)
    assert source == "supabase"


# --- failure signalling -----------------------------------------------------


def test_main_returns_nonzero_and_alerts_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    alerts: list[str] = []
    monkeypatch.setattr(alpha_main, "send_alert", alerts.append)
    monkeypatch.setattr(
        alpha_main, "run_system", lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    assert alpha_main.main() == 1
    assert alerts and "db down" in alerts[0]


def test_main_returns_zero_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(alpha_main, "run_system", lambda: None)
    assert alpha_main.main() == 0


def test_plan_table_never_overwrites_a_value_with_null() -> None:
    existing = [{"ticker": "AAPL", "price": 10.0, "atr": 2.0}]
    inserts, updates = insert_daily.plan_table(
        existing, [{"ticker": "AAPL", "date": "d", "price": 11.0, "atr": None}]
    )
    assert inserts == [] and updates == [("AAPL", {"price": 11.0})]


def test_option_score_is_stored_in_every_table(fake_client: FakeSupabase) -> None:
    """Regression: 'Option Score' had no column mapping, so option_score was NULL everywhere."""
    df = _scored_df()
    insert_daily.sync_day(df, _weekly(df), day="2026-12-01")
    for table in ("daily_metrics", "option_scores", "weekly_watchlist"):
        scores = {r["ticker"]: r["option_score"] for r in fake_client.tables[table]}
        assert scores == {"AAPL": 8, "MSFT": 6}, table
