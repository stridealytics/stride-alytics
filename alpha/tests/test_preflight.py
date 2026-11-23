"""Preflight: all missing settings are reported together, before any work starts."""

from __future__ import annotations

import json

import pytest

from app import main
from app.preflight import check_environment

FULL = {"SUPABASE_URL": "u", "SUPABASE_KEY": "k"}


def test_missing_supabase_settings_are_all_listed() -> None:
    result = check_environment({}, have_service_file=False)
    assert not result.ok and len(result.errors) == 2
    assert "SUPABASE_URL" in result.errors[0] and "SUPABASE_KEY" in result.errors[1]


def test_minimal_valid_setup_only_adds_notes() -> None:
    result = check_environment(FULL, have_service_file=False)
    assert result.ok and len(result.notes) == 2  # Sheets skipped, no alerts


def test_sample_run_needs_no_supabase() -> None:
    assert check_environment({}, allow_sample=True, have_service_file=False).ok


def test_sheets_id_without_credentials_is_an_error() -> None:
    env = {**FULL, "GOOGLE_SHEETS_SPREADSHEET_ID": "sid"}
    assert not check_environment(env, have_service_file=False).ok
    assert check_environment(
        {**env, "GOOGLE_SERVICE_ACCOUNT_JSON": "{}"}, have_service_file=False
    ).ok
    assert check_environment(env, have_service_file=True).ok


def test_webhook_removes_the_alert_note() -> None:
    notes = check_environment({**FULL, "SLACK_WEBHOOK_URL": "x"}, have_service_file=False).notes
    assert not any("webhook" in n for n in notes)


def test_run_fails_before_loading_data_when_setup_is_incomplete(monkeypatch) -> None:
    for name in ("SUPABASE_URL", "SUPABASE_KEY", "GOOGLE_SHEETS_SPREADSHEET_ID"):
        monkeypatch.delenv(name, raising=False)

    def must_not_load(*_):
        raise AssertionError("data was loaded before the preflight check")

    monkeypatch.setattr(main, "_load_data", must_not_load)
    with pytest.raises(RuntimeError, match="Setup incomplete"):
        main.run_system(allow_sample=False)


FAKE_KEY = json.dumps(
    {
        "type": "service_account",
        "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE-NOT-A-REAL-KEY\n-----END PRIVATE KEY-----\n",
        "client_email": "fake@fake-project.iam.gserviceaccount.com",
    }
)
REAL_LOOKING = json.dumps(
    {
        "type": "service_account",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE\n",
        "client_email": "bot@proj.iam.gserviceaccount.com",
    }
)


def test_the_fake_placeholder_key_skips_sheets_instead_of_calling_google() -> None:
    result = check_environment(
        {**FULL, "GOOGLE_SHEETS_SPREADSHEET_ID": "sheet", "GOOGLE_SERVICE_ACCOUNT_JSON": FAKE_KEY},
        have_service_file=False,
    )
    assert result.ok and result.skip_sheets
    assert any("fake placeholder" in n for n in result.notes)


def test_a_real_looking_key_is_not_treated_as_a_placeholder() -> None:
    from app.preflight import is_placeholder_credentials

    assert not is_placeholder_credentials(REAL_LOOKING)
    assert not is_placeholder_credentials("not json") and not is_placeholder_credentials(None)
    env = {
        **FULL,
        "GOOGLE_SHEETS_SPREADSHEET_ID": "sheet",
        "GOOGLE_SERVICE_ACCOUNT_JSON": REAL_LOOKING,
    }
    assert not check_environment(env, have_service_file=False).skip_sheets
