"""Check the environment before any work starts and report everything that is missing at once."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field


def is_placeholder_credentials(text: str | None) -> bool:
    """True for the fake service-account JSON used for local work (never a working key)."""
    if not text:
        return False
    try:
        info = json.loads(text)
    except ValueError:
        return False
    if not isinstance(info, dict):
        return False
    return "FAKE" in str(info.get("private_key", "")) or str(info.get("client_email", "")).endswith(
        "@fake-project.iam.gserviceaccount.com"
    )


def _credential_text(env: Mapping[str, str]) -> str | None:
    if env.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return env["GOOGLE_SERVICE_ACCOUNT_JSON"]
    for path in ("service_account.json", "../service_account.json"):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read()
    return None


@dataclass
class Preflight:
    errors: list[str] = field(default_factory=list)  # the run cannot work without these
    notes: list[str] = field(default_factory=list)  # optional features that will be skipped
    skip_sheets: bool = False  # the credentials are a placeholder, so do not call Google

    @property
    def ok(self) -> bool:
        return not self.errors


def check_environment(
    env: Mapping[str, str] | None = None,
    *,
    allow_sample: bool = False,
    have_service_file: bool | None = None,
) -> Preflight:
    """What the run needs. Supabase is required unless this is a sample-data demo run."""
    env = os.environ if env is None else env
    result = Preflight()

    if allow_sample:
        result.notes.append("Sample-data run: nothing is written to Supabase or Google Sheets.")
    else:
        for name in ("SUPABASE_URL", "SUPABASE_KEY"):
            if not env.get(name):
                result.errors.append(f"{name} is not set (needed to write results to Supabase).")

    expected = env.get("ALPHA_EXPECT_PROJECT")
    if expected and env.get("SUPABASE_URL") and expected not in env["SUPABASE_URL"]:
        result.errors.append(
            f"SUPABASE_URL does not match ALPHA_EXPECT_PROJECT ({expected!r}): refusing to run "
            "against a different Supabase project than the one you named."
        )
    if env.get("ALPHA_DRY_RUN") == "1":
        result.notes.append("Dry run: nothing will be written.")

    if env.get("GOOGLE_SHEETS_SPREADSHEET_ID"):
        if have_service_file is None:
            have_service_file = os.path.exists("service_account.json") or os.path.exists(
                "../service_account.json"
            )
        if not env.get("GOOGLE_SERVICE_ACCOUNT_JSON") and not have_service_file:
            result.errors.append(
                "GOOGLE_SHEETS_SPREADSHEET_ID is set but there are no Google credentials "
                "(set GOOGLE_SERVICE_ACCOUNT_JSON or add service_account.json)."
            )
        elif is_placeholder_credentials(_credential_text(env)):
            result.skip_sheets = True
            result.notes.append(
                "Google Sheets push skipped: the credentials are the fake placeholder key. "
                "Add a real key to push for real."
            )
    else:
        result.notes.append("Google Sheets push skipped (GOOGLE_SHEETS_SPREADSHEET_ID not set).")

    if not (env.get("SLACK_WEBHOOK_URL") or env.get("DISCORD_WEBHOOK_URL")):
        result.notes.append("No Slack or Discord webhook set: failures will not send alerts.")
    return result
