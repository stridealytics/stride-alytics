"""
Alpha Stock and Options Screening Pipeline — Config Loader
Loads environment variables and exposes them as a typed config object.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

# Load .env file
load_dotenv()


def _get_setting(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value

    try:
        return st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        return None


@dataclass
class Config:
    # Supabase
    SUPABASE_URL: str | None = None
    SUPABASE_KEY: str | None = None

    # APIs
    POLYGON_API_KEY: str | None = None
    FMP_API_KEY: str | None = None
    MASSIVE_API_KEY: str | None = None

    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_JSON: str | None = None
    GOOGLE_SHEETS_SPREADSHEET_ID: str | None = None

    # Optional integrations
    SLACK_WEBHOOK_URL: str | None = None
    DISCORD_WEBHOOK_URL: str | None = None

    # Internal API token (optional)
    API_AUTH_TOKEN: str | None = None


config = Config(
    SUPABASE_URL=_get_setting("SUPABASE_URL"),
    SUPABASE_KEY=_get_setting("SUPABASE_KEY"),
    POLYGON_API_KEY=_get_setting("POLYGON_API_KEY"),
    FMP_API_KEY=_get_setting("FMP_API_KEY"),
    MASSIVE_API_KEY=_get_setting("MASSIVE_API_KEY"),
    GOOGLE_SERVICE_ACCOUNT_JSON=_get_setting("GOOGLE_SERVICE_ACCOUNT_JSON"),
    GOOGLE_SHEETS_SPREADSHEET_ID=_get_setting("GOOGLE_SHEETS_SPREADSHEET_ID"),
    SLACK_WEBHOOK_URL=_get_setting("SLACK_WEBHOOK_URL"),
    DISCORD_WEBHOOK_URL=_get_setting("DISCORD_WEBHOOK_URL"),
    API_AUTH_TOKEN=_get_setting("API_AUTH_TOKEN"),
)
