"""Daily returns per symbol (yfinance, cached) for the correlation rule BR-013.

Best-effort: a symbol whose history cannot be fetched returns ``None`` and the gate then blocks
(fail-safe). Blocking network call: callers use a thread. Injected so tests can substitute a fake.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from app.utils.logger import get_logger

log = get_logger(__name__)

CACHE_TTL_SECONDS = 6 * 3600  # daily returns barely change within a day
LOOKBACK = "6mo"

ReturnsProvider = Callable[[str], list[float] | None]

_lock = threading.Lock()
_cache: dict[str, tuple[float, list[float]]] = {}


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def fetch_returns(symbol: str) -> list[float] | None:
    now = time.monotonic()
    with _lock:
        hit = _cache.get(symbol)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    try:
        import yfinance as yf

        closes = yf.Ticker(symbol).history(period=LOOKBACK)["Close"].dropna().tolist()
    except Exception as exc:  # noqa: BLE001
        log.warning("returns_data.failed", symbol=symbol, error=str(exc))
        return None
    if len(closes) < 2:
        return None
    returns = [b / a - 1.0 for a, b in zip(closes, closes[1:]) if a]
    with _lock:
        _cache[symbol] = (now, returns)
    return returns


def get_returns_provider() -> ReturnsProvider:
    """FastAPI dependency; tests override it with a fake."""
    return fetch_returns
