"""
Push DataFrames to Google Sheets using the Sheets REST API (requests library).
"""

import json
import os
import urllib.parse

import pandas as pd
import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_creds():
    """Get Google service account credentials."""
    val = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if val:
        return Credentials.from_service_account_info(json.loads(val), scopes=SCOPES)
    for p in ["service_account.json", "../service_account.json"]:
        if os.path.exists(p):
            return Credentials.from_service_account_file(p, scopes=SCOPES)
    raise FileNotFoundError(
        "No Google service account credentials found. "
        "Set GOOGLE_SERVICE_ACCOUNT_JSON env var or place service_account.json."
    )


def _api(method: str, url: str, body: dict | None = None) -> dict:
    """Authenticated Google Sheets API call using requests library."""
    creds = _get_creds()
    creds.refresh(Request())
    headers = {"Authorization": "Bearer " + creds.token, "Content-Type": "application/json"}
    r = requests.request(method, url, json=body, headers=headers, timeout=20)
    if not r.ok:
        raise RuntimeError(f"Google API error {r.status_code}: {r.text[:300]}")
    return r.json()


def _col_letter(n: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _cell(value) -> str:
    """One cell as text. Missing values are blank, not 'nan'."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value)


def _grid_size(sid: str, name: str) -> tuple[int, int] | None:
    """(rows, columns) of the worksheet, or None if it does not exist."""
    data = _api(
        "GET", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=sheets.properties"
    )
    for sheet in data.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == name:
            grid = props.get("gridProperties", {})
            return grid.get("rowCount", 0), grid.get("columnCount", 0)
    return None


def _ensure_worksheet(sid: str, name: str, rows: int, cols: int) -> None:
    """Create the worksheet, or grow it so ``rows`` x ``cols`` fit."""
    rows, cols = max(rows, 500), max(cols, 26)
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate"
    size = _grid_size(sid, name)
    if size is None:
        grid = {"rowCount": rows, "columnCount": cols}
        _api(
            "POST",
            url,
            {"requests": [{"addSheet": {"properties": {"title": name, "gridProperties": grid}}}]},
        )
    elif size[0] < rows or size[1] < cols:
        grid = {"rowCount": max(size[0], rows), "columnCount": max(size[1], cols)}
        props = {"title": name, "gridProperties": grid}
        update = {"updateSheetProperties": {"properties": props, "fields": "title,gridProperties"}}
        # updateSheetProperties needs the numeric sheetId, so look it up.
        meta = _api(
            "GET", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=sheets.properties"
        )
        for sheet in meta.get("sheets", []):
            if sheet["properties"].get("title") == name:
                update["updateSheetProperties"]["properties"]["sheetId"] = sheet["properties"][
                    "sheetId"
                ]
        _api("POST", url, {"requests": [update]})


def push_to_sheet(df: pd.DataFrame, sheet_name: str) -> None:
    """
    Push a DataFrame to a specific worksheet.
    Requires GOOGLE_SHEETS_SPREADSHEET_ID in .env or env.
    The spreadsheet must already exist and be shared with the service account email.

    Values are written as plain text (``RAW``), so a cell that starts with ``=`` is never run as
    a formula. The sheet is cleared in full first, so a shorter push leaves no old rows behind,
    and any number of rows or columns is supported.
    """
    sid = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    if not sid:
        raise RuntimeError(
            "GOOGLE_SHEETS_SPREADSHEET_ID is not set. "
            "Add it to alpha/.env or set it as an environment variable."
        )

    values = [[_cell(c) for c in df.columns]] + [
        [_cell(v) for v in row] for row in df.to_numpy().tolist()
    ]
    width = max(len(values[0]), 1)

    _ensure_worksheet(sid, sheet_name, len(values), width)

    encoded_name = urllib.parse.quote(sheet_name)
    _api(
        "POST",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{encoded_name}:clear",
        {},
    )
    _api(
        "PUT",
        f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/{encoded_name}!A1:{_col_letter(width)}{len(values)}?valueInputOption=RAW",
        {"values": values},
    )
    print(f"[GSHEETS] Pushed {len(df)} rows to '{sheet_name}'")
