"""Check the environment before any work starts and report everything that is missing at once."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass
class Preflight:
    errors: list[str] = field(default_factory=list)  # the run cannot work without these
    notes: list[str] = field(default_factory=list)  # optional features that will be skipped

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
    else:
        result.notes.append("Google Sheets push skipped (GOOGLE_SHEETS_SPREADSHEET_ID not set).")

    if not (env.get("SLACK_WEBHOOK_URL") or env.get("DISCORD_WEBHOOK_URL")):
        result.notes.append("No Slack or Discord webhook set: failures will not send alerts.")
    return result
