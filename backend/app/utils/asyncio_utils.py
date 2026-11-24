"""Asyncio helpers for platform-specific database requirements."""

import asyncio
import sys
from collections.abc import Callable


def psycopg_loop_factory() -> Callable[[], asyncio.AbstractEventLoop] | None:
    """Return the event-loop factory required by Psycopg on Windows."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop
    return None
