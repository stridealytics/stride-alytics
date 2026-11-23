"""
Dynamic Ticker Universe Loader for the Alpha Stock and Options Screening Pipeline.

Supports multiple sources:
- S&P 500 constituents (public index constituent lists, scraped)
- NASDAQ 100 constituents (public index constituent lists, scraped)
- Most active tickers (FMP API)
- Custom watchlist (local CSV / Supabase)
"""

import os

import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from app.config import config

load_dotenv()


HEADERS = {"User-Agent": "StrideAlytics-alpha/1.0 (personal screener; ticker list refresh)"}


def table_column(html: str, header: str, table_id: str = "constituents") -> list[str]:
    """Text of the ``header`` column of the table with ``table_id`` (empty list if not found).

    Parsed with BeautifulSoup alone, so no lxml/html5lib dependency is needed.
    """
    table = BeautifulSoup(html, "html.parser").find("table", {"id": table_id})
    if table is None:
        return []
    rows = table.find_all("tr")
    if not rows:
        return []
    names = [c.get_text(strip=True) for c in rows[0].find_all(["th", "td"])]
    if header not in names:
        return []
    idx = names.index(header)
    values = []
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) > idx and cells[idx].get_text(strip=True):
            values.append(cells[idx].get_text(strip=True))
    return values


def get_sp500_tickers() -> list[str]:
    """Fetch S&P 500 constituents from a public index constituent list (scraped)."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        tickers = table_column(resp.text, "Symbol")
        return [str(t).replace(".", "-") for t in tickers]
    except Exception as e:
        print(f"⚠️ Failed to fetch S&P 500 tickers: {e}")
        return []


def get_nasdaq100_tickers() -> list[str]:
    """Fetch NASDAQ 100 constituents from a public index constituent list (scraped)."""
    url = "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        tickers = table_column(resp.text, "Ticker")
        return [str(t).replace(".", "-") for t in tickers]
    except Exception as e:
        print(f"⚠️ Failed to fetch NASDAQ 100 tickers: {e}")
        return []


def get_most_active_tickers(limit: int = 200) -> list[str]:
    """Fetch most active tickers from FMP API."""
    if not config.FMP_API_KEY:
        return []
    try:
        url = f"https://financialmodelingprep.com/api/v3/actives?apikey={config.FMP_API_KEY}"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        tickers = [item["ticker"] for item in data[:limit]]
        return tickers
    except Exception as e:
        print(f"⚠️ Failed to fetch most active tickers: {e}")
        return []


def get_custom_universe() -> list[str]:
    """Load custom ticker universe from alpha/universe/ directory."""
    universe_dir = "universe"
    if not os.path.exists(universe_dir):
        return []
    tickers = set()
    for fname in os.listdir(universe_dir):
        if fname.endswith(".csv"):
            fpath = os.path.join(universe_dir, fname)
            try:
                df = pd.read_csv(fpath)
                if "ticker" in df.columns:
                    tickers.update(df["ticker"].tolist())
                elif "Ticker" in df.columns:
                    tickers.update(df["Ticker"].tolist())
            except Exception as e:
                print(f"⚠️ Failed to read {fpath}: {e}")
    return sorted(list(tickers))


# The persistent master list lives in app/database/universe.py (sync_universe).


def load_tickers(
    use_sp500: bool = True,
    use_nasdaq100: bool = True,
    use_most_active: bool = True,
    use_custom: bool = True,
    max_total: int = 2000,
) -> list[str]:
    """
    Load the full trading universe for ingestion.

    Parameters
    ----------
    use_sp500 : bool
        Include S&P 500 constituents.
    use_nasdaq100 : bool
        Include NASDAQ 100 constituents.
    use_most_active : bool
        Include most active stocks from FMP.
    use_custom : bool
        Include custom watchlist from universe/ directory.
    max_total : int
        Maximum number of tickers to return (deduplicated).

    Returns
    -------
    list[str]
        Deduplicated list of ticker symbols.
    """
    sources = []
    if use_sp500:
        sources.append(("SP500", get_sp500_tickers()))
    if use_nasdaq100:
        sources.append(("NASDAQ100", get_nasdaq100_tickers()))
    if use_most_active:
        sources.append(("MOST_ACTIVE", get_most_active_tickers()))
    if use_custom:
        sources.append(("CUSTOM", get_custom_universe()))

    # Deduplicate while preserving order
    seen = set()
    tickers = []
    for source_name, source_tickers in sources:
        if not source_tickers and source_name in ("SP500", "NASDAQ100"):
            # A scraped index list came back empty: the page changed or the site blocked us.
            from app.utils.notify import send_alert

            print(f"[WARNING] {source_name} ticker list is empty (fetch failed?)")
            send_alert(f"Alpha: the {source_name} ticker list came back empty.")
        added = 0
        for t in source_tickers:
            if t not in seen:
                seen.add(t)
                tickers.append(t)
                added += 1
        print(f"📥 Added {added} tickers from {source_name}")

    # Trim to max
    tickers = tickers[:max_total]
    print(f"✅ Total universe size: {len(tickers)} tickers")
    return tickers
