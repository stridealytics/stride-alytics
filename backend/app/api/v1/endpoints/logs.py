"""Read-only access to the append-only signal and audit logs (FR-700–730)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import json

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import Ctx, get_ctx, to_csv

router = APIRouter()

AUDIT_CSV_COLUMNS = ["occurred_at", "action", "entity", "entity_id", "before", "after"]


@router.get("/signals")
async def list_signals(
    start: datetime | None = None,
    end: datetime | None = None,
    symbol: str | None = Query(default=None, max_length=16),
    rule_id: str | None = Query(default=None, max_length=16),
    decision: str | None = Query(default=None, pattern="^(allowed|blocked|info)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: Ctx = Depends(get_ctx),
) -> dict[str, Any]:
    """Rule/gate decisions, including blocked signals."""
    rows, total = await ctx.repo.list_signals(
        ctx.user_id,
        start=start,
        end=end,
        symbol=symbol,
        rule_id=rule_id,
        decision=decision,
        limit=limit,
        offset=offset,
    )
    return {"success": True, "data": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/audit")
async def list_audit(
    start: datetime | None = None,
    end: datetime | None = None,
    entity: str | None = Query(default=None, max_length=32),
    action: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: Ctx = Depends(get_ctx),
) -> dict[str, Any]:
    """Changes to trades, portfolios, watchlists and settings."""
    rows, total = await ctx.repo.list_audit(
        ctx.user_id,
        start=start,
        end=end,
        entity=entity,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {"success": True, "data": rows, "total": total, "limit": limit, "offset": offset}


# NOTE: declared as a separate path so "audit.csv" is never parsed as a filter value.
@router.get("/audit.csv")
async def export_audit(
    start: datetime | None = None,
    end: datetime | None = None,
    entity: str | None = Query(default=None, max_length=32),
    action: str | None = Query(default=None, max_length=32),
    ctx: Ctx = Depends(get_ctx),
) -> Response:
    """CSV export of the audit log for a period (BR-064). Newest first; before/after as JSON."""
    # Page through everything so a long period is never silently cut off.
    rows: list[dict[str, Any]] = []
    page = 1_000
    while True:
        chunk, total = await ctx.repo.list_audit(
            ctx.user_id,
            start=start,
            end=end,
            entity=entity,
            action=action,
            limit=page,
            offset=len(rows),
        )
        rows.extend(chunk)
        if not chunk or len(rows) >= total:
            break
    flat = [
        {
            **r,
            "before": json.dumps(r["before"], sort_keys=True),
            "after": json.dumps(r["after"], sort_keys=True),
        }
        for r in rows
    ]
    return Response(
        content=to_csv(AUDIT_CSV_COLUMNS, flat),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit.csv"'},
    )
