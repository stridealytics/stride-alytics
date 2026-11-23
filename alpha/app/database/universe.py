"""The master list of tickers (``ticker_universe``): loaded once, then only changes are applied.

Each ticker has exactly one row. A daily sync compares today's fresh list with the stored one and
writes only the difference:

* a ticker not stored yet is **added** (inserted once; existing rows are never overwritten);
* a stored ticker missing from the fresh list is **soft-removed** (``status = 'removed'``, history
  and old rows stay); one that returns is **reactivated**;
* nothing else is touched, so an unchanged universe means zero writes.

Mass-removal guard: an empty fresh list, or one that would remove more than
``UNIVERSE_MAX_REMOVE_PCT`` percent (default 20) of the active tickers, is treated as a bad fetch
(an outage or a changed web page). Additions still happen; removals are skipped and reported.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

TABLE = "ticker_universe"
PAGE = 1000
CHUNK = 500
DEFAULT_MAX_REMOVE_PCT = 20.0
MIN_REMOVALS_ALWAYS_OK = 5  # small lists are never "mass" removals


@dataclass
class SyncPlan:
    add: list[str] = field(default_factory=list)
    reactivate: list[str] = field(default_factory=list)
    remove: list[str] = field(default_factory=list)
    removal_skipped: str | None = None  # why removals were held back, if they were

    @property
    def changes(self) -> int:
        return len(self.add) + len(self.reactivate) + len(self.remove)

    def summary(self) -> dict:
        return {
            "added": len(self.add),
            "reactivated": len(self.reactivate),
            "removed": len(self.remove),
            "removal_skipped": self.removal_skipped,
        }


def clean(tickers: list[str]) -> list[str]:
    """Upper-case, trimmed, de-duplicated, order preserved; blanks dropped."""
    seen: dict[str, None] = {}
    for t in tickers:
        t = str(t).strip().upper()
        if t and t != "NAN":
            seen.setdefault(t, None)
    return list(seen)


def plan_sync(
    stored: dict[str, dict], fresh: list[str], max_remove_pct: float = DEFAULT_MAX_REMOVE_PCT
) -> SyncPlan:
    """Pure: the smallest set of changes that makes the stored list match ``fresh``."""
    fresh = clean(fresh)
    plan = SyncPlan()
    if not fresh:
        plan.removal_skipped = "the fresh ticker list is empty (treated as a failed fetch)"
        return plan

    fresh_set = set(fresh)
    plan.add = [t for t in fresh if t not in stored]
    plan.reactivate = [t for t in fresh if t in stored and stored[t].get("status") == "removed"]

    gone = sorted(
        t for t, r in stored.items() if r.get("status") != "removed" and t not in fresh_set
    )
    active = sum(1 for r in stored.values() if r.get("status") != "removed")
    limit = max(MIN_REMOVALS_ALWAYS_OK, active * max_remove_pct / 100)
    if len(gone) > limit:
        plan.removal_skipped = (
            f"{len(gone)} of {active} active tickers would be removed (limit {limit:.0f}); "
            "looks like a bad fetch, so none were removed"
        )
    else:
        plan.remove = gone
    return plan


def _client():
    from app.database.supabase_client import get_supabase_client

    return get_supabase_client()


def fetch_universe(client=None) -> dict[str, dict]:
    """Every stored row, keyed by ticker (paged so the 1000-row API limit never truncates)."""
    client = client or _client()
    rows: dict[str, dict] = {}
    start = 0
    while True:
        page = client.table(TABLE).select("*").range(start, start + PAGE - 1).execute().data or []
        for r in page:
            rows[str(r["ticker"]).upper()] = r
        if len(page) < PAGE:
            return rows
        start += PAGE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_plan(plan: SyncPlan, source: str, client=None) -> None:
    """Write a plan: inserts for new tickers, status updates for the rest. Nothing is deleted."""
    client = client or _client()
    now = _now()
    new_rows = [
        {"ticker": t, "status": "active", "source": source, "added_at": now} for t in plan.add
    ]
    for i in range(0, len(new_rows), CHUNK):
        client.table(TABLE).insert(new_rows[i : i + CHUNK]).execute()
    for i in range(0, len(plan.reactivate), CHUNK):
        client.table(TABLE).update({"status": "active", "removed_at": None}).in_(
            "ticker", plan.reactivate[i : i + CHUNK]
        ).execute()
    for i in range(0, len(plan.remove), CHUNK):
        client.table(TABLE).update({"status": "removed", "removed_at": now}).in_(
            "ticker", plan.remove[i : i + CHUNK]
        ).execute()


def sync_universe(fresh: list[str], source: str = "universe_scanner", client=None) -> SyncPlan:
    """Bring ``ticker_universe`` in line with ``fresh`` by writing only the difference."""
    client = client or _client()
    max_pct = float(os.getenv("UNIVERSE_MAX_REMOVE_PCT", DEFAULT_MAX_REMOVE_PCT))
    stored = fetch_universe(client)
    plan = plan_sync(stored, fresh, max_pct)
    from .safety import dry_run

    if plan.changes and not dry_run():
        apply_plan(plan, source, client)
    return plan


def active_tickers(client=None) -> list[str]:
    """The tickers currently in the universe, sorted."""
    stored = fetch_universe(client)
    return sorted(t for t, r in stored.items() if r.get("status") != "removed")


def fill_sectors(sectors: dict[str, str], client=None) -> int:
    """Set the sector once for tickers that have none yet; stored sectors are never overwritten."""
    client = client or _client()
    stored = fetch_universe(client)
    todo = {t: s for t, s in sectors.items() if s and t in stored and not stored[t].get("sector")}
    for t, s in todo.items():
        # stored spelling: `stored` is keyed upper-case but .eq() is case-sensitive
        client.table(TABLE).update({"sector": s}).eq("ticker", stored[t]["ticker"]).execute()
    return len(todo)
