"""Google Sheets push: formula safety, size limits and blank handling (fake API, no network)."""

from __future__ import annotations

import pandas as pd
import pytest

from app.sheets import push_to_sheets as sheets


class FakeApi:
    def __init__(self, grid: tuple[int, int] | None = None) -> None:
        self.grid = grid
        self.calls: list[tuple[str, str, dict | None]] = []

    def __call__(self, method: str, url: str, body: dict | None = None) -> dict:
        self.calls.append((method, url, body))
        if method == "GET":
            if self.grid is None:
                return {"sheets": []}
            rows, cols = self.grid
            props = {
                "title": "Daily",
                "sheetId": 7,
                "gridProperties": {"rowCount": rows, "columnCount": cols},
            }
            return {"sheets": [{"properties": props}]}
        return {}


@pytest.fixture
def api(monkeypatch):
    fake = FakeApi()
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "SID")
    monkeypatch.setattr(sheets, "_api", fake)
    return fake


def _put(api: FakeApi) -> tuple[str, dict]:
    method, url, body = [c for c in api.calls if c[0] == "PUT"][0]
    return url, body


def test_column_letters_go_past_z() -> None:
    assert [sheets._col_letter(n) for n in (1, 26, 27, 52, 53)] == ["A", "Z", "AA", "AZ", "BA"]


def test_values_are_written_raw_so_formulas_do_not_run(api) -> None:
    sheets.push_to_sheet(pd.DataFrame({"Ticker": ['=HYPERLINK("http://x","a")']}), "Daily")
    url, body = _put(api)
    assert "valueInputOption=RAW" in url and "USER_ENTERED" not in url
    assert body["values"][1] == ['=HYPERLINK("http://x","a")']


def test_more_than_26_columns_and_500_rows_are_supported(api) -> None:
    df = pd.DataFrame([[i] * 30 for i in range(600)], columns=[f"c{i}" for i in range(30)])
    sheets.push_to_sheet(df, "Daily")
    url, _ = _put(api)
    assert "!A1:AD601?" in url
    add = [c for c in api.calls if c[0] == "POST" and c[2] and "requests" in c[2]][0][2]
    grid = add["requests"][0]["addSheet"]["properties"]["gridProperties"]
    assert grid == {"rowCount": 601, "columnCount": 30}


def test_existing_small_sheet_is_grown(monkeypatch) -> None:
    fake = FakeApi(grid=(500, 26))
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "SID")
    monkeypatch.setattr(sheets, "_api", fake)
    sheets.push_to_sheet(pd.DataFrame([[1] * 3] * 700, columns=list("abc")), "Daily")
    update = [c for c in fake.calls if c[0] == "POST" and c[2] and "requests" in c[2]][0][2][
        "requests"
    ][0]
    props = update["updateSheetProperties"]["properties"]
    assert props["sheetId"] == 7 and props["gridProperties"]["rowCount"] == 701


def test_whole_sheet_is_cleared_and_blanks_are_empty(api) -> None:
    sheets.push_to_sheet(pd.DataFrame({"a": [1.0, float("nan")], "b": [None, "x"]}), "Daily")
    clear = [c for c in api.calls if c[1].endswith(":clear")][0]
    assert "A1:Z500" not in clear[1]
    assert _put(api)[1]["values"] == [["a", "b"], ["1.0", ""], ["", "x"]]


def test_a_failed_clear_is_not_swallowed(monkeypatch) -> None:
    def boom(method, url, body=None):
        if url.endswith(":clear"):
            raise RuntimeError("clear failed")
        return {
            "sheets": [
                {
                    "properties": {
                        "title": "Daily",
                        "sheetId": 1,
                        "gridProperties": {"rowCount": 900, "columnCount": 30},
                    }
                }
            ]
        }

    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "SID")
    monkeypatch.setattr(sheets, "_api", boom)
    with pytest.raises(RuntimeError, match="clear failed"):
        sheets.push_to_sheet(pd.DataFrame({"a": [1]}), "Daily")
