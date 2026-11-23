"""Protection against wiping the data once it has been loaded properly.

After the first complete load the pipeline writes ``initial_load_complete`` to the ``alpha_state``
table. From then on every bulk-destructive helper (``clear_all_tables``, ``delete_rows``) refuses to
run. It is fail-safe: if the flag cannot be read, the operation is blocked too. To override on
purpose (for example to rebuild a corrupted day), set the environment variable
``ALPHA_UNLOCK_DESTRUCTIVE`` to the text ``I-UNDERSTAND`` for that one command.

The daily run itself never needs this: it only adds, updates and soft-removes.
"""

from __future__ import annotations

import os

STATE_TABLE = "alpha_state"
LOAD_FLAG = "initial_load_complete"
UNLOCK_ENV = "ALPHA_UNLOCK_DESTRUCTIVE"
UNLOCK_VALUE = "I-UNDERSTAND"


DRY_RUN_ENV = "ALPHA_DRY_RUN"


def dry_run() -> bool:
    """True when the run must only read and report (``--dry-run`` or ``ALPHA_DRY_RUN=1``)."""
    return os.getenv(DRY_RUN_ENV) == "1"


class DestructiveOperationBlockedError(RuntimeError):
    """A bulk delete was refused because the data has been loaded and is now protected."""


def _client():
    from app.database.supabase_client import get_supabase_client

    return get_supabase_client()


def is_loaded(client=None) -> bool:
    """True when the initial load has been completed. Raises if the state cannot be read."""
    client = client or _client()
    rows = client.table(STATE_TABLE).select("value").eq("key", LOAD_FLAG).execute().data or []
    return bool(rows) and str(rows[0].get("value")).lower() == "true"


def mark_loaded(client=None) -> bool:
    """Record that the initial load is complete. Returns True if this call set it."""
    client = client or _client()
    if is_loaded(client):
        return False
    client.table(STATE_TABLE).insert({"key": LOAD_FLAG, "value": "true"}).execute()
    return True


def require_unlocked(action: str, client=None) -> None:
    """Raise ``DestructiveOperationBlockedError`` unless it is safe to run ``action``."""
    if os.getenv(UNLOCK_ENV) == UNLOCK_VALUE:
        print(f"[WARNING] {UNLOCK_ENV} is set: allowing destructive action '{action}'.")
        return
    try:
        locked = is_loaded(client)
    except Exception as exc:  # noqa: BLE001 - cannot verify, so do not allow
        raise DestructiveOperationBlockedError(
            f"Refusing '{action}': could not check whether the data is protected ({exc})."
        ) from exc
    if locked:
        raise DestructiveOperationBlockedError(
            f"Refusing '{action}': the data has been loaded and is protected. The daily run only "
            f"adds, updates and soft-removes. To override on purpose, set {UNLOCK_ENV}={UNLOCK_VALUE}."
        )
