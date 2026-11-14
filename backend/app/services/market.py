"""Market data service — owns all external data fetching + fallbacks.

The endpoint layer (``app.api.v1.endpoints.market``) must remain a thin
adapter that delegates here. The reasoning:

* Centralizes URL, headers, timeouts, and retries.
* Makes the data source swappable without touching HTTP plumbing.
* Allows tests to monkeypatch this module.
* Keeps schemas separate from business logic.
"""

from __future__ import annotations

import asyncio
from typing import Final, Literal

from app.api.v1.schemas.market import TickerData
from app.utils.logger import get_logger

DEFAULT_TICKERS: Final[tuple[str, ...]] = ("SPY", "QQQ", "DIA", "VIX")

# Static placeholder values used when Yahoo is unreachable. These are NOT live
# prices: responses that use them are labelled ``source="fallback"`` so the UI
# can say so.
MOCK_TICKERS: Final[dict[str, TickerData]] = {
    "SPY": TickerData(symbol="SPY", price="548.32", change="-1.23", changePercent="-0.22"),
    "QQQ": TickerData(symbol="QQQ", price="478.92", change="2.15", changePercent="+0.45"),
    "DIA": TickerData(symbol="DIA", price="395.61", change="0.89", changePercent="+0.22"),
    "VIX": TickerData(symbol="VIX", price="15.42", change="-0.58", changePercent="-3.63"),
}

TickerSource = Literal["live", "fallback"]

log = get_logger(__name__)


# Yahoo's own symbol for an index differs from the name shown in the UI.
YAHOO_SYMBOL: Final[dict[str, str]] = {"VIX": "^VIX"}


def _fetch_quotes_sync(symbols: tuple[str, ...]) -> dict[str, TickerData]:
    """Quotes via yfinance (blocking; run in a thread). Skips any symbol with no price.

    The old direct call to Yahoo's v7 quote endpoint returns 401 (it needs a crumb), so the
    ticker strip was always showing placeholder values.
    """
    import yfinance as yf

    result: dict[str, TickerData] = {}
    for sym in symbols:
        try:
            info = yf.Ticker(YAHOO_SYMBOL.get(sym, sym)).fast_info
            last, prev = float(info["last_price"]), float(info["previous_close"])
        except Exception as exc:  # noqa: BLE001 - one bad symbol must not fail the rest
            log.warning("market.ticker_skipped", symbol=sym, error=str(exc))
            continue
        if not (last > 0 and prev > 0):
            continue
        result[sym] = TickerData(
            symbol=sym,
            price=str(round(last, 2)),
            change=str(round(last - prev, 2)),
            changePercent=str(round((last / prev - 1) * 100, 2)),
        )
    return result


async def fetch_tickers_with_source(
    symbols: tuple[str, ...] = DEFAULT_TICKERS,
) -> tuple[dict[str, TickerData], TickerSource]:
    """Fetch ticker data for ``symbols`` and say where it came from.

    Always returns a non-empty ``{ SYM: TickerData }`` map. If nothing could be fetched it returns
    :data:`MOCK_TICKERS` with source ``"fallback"`` so callers can tell the numbers are not live.
    """
    fallback: tuple[dict[str, TickerData], TickerSource] = (dict(MOCK_TICKERS), "fallback")
    try:
        log.info("market.tickers_fetching", symbols=",".join(symbols))
        result = await asyncio.to_thread(_fetch_quotes_sync, symbols)
    except Exception as exc:  # last-resort fallback so the UI never breaks
        log.error("market.tickers_failed", error=str(exc), error_type=type(exc).__name__)
        return fallback
    if not result:
        log.warning("market.tickers_no_results")
        return fallback
    log.info("market.tickers_served", ticker_count=len(result), symbols=list(result))
    return result, "live"


async def fetch_tickers(symbols: tuple[str, ...] = DEFAULT_TICKERS) -> dict[str, TickerData]:
    """Like :func:`fetch_tickers_with_source` but returns only the data map."""
    data, _ = await fetch_tickers_with_source(symbols)
    return data
