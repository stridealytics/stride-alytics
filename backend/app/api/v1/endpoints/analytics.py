"""Performance analytics: how realised results compare with expectations (FR-920)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import Ctx, get_ctx
from app.domain.ev import calibration
from app.services.portfolio import calculate_pnl

router = APIRouter()


@router.get("/ev-calibration")
async def ev_calibration(ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    """Win rate, average P&L and average entry EV of closed trades by layer.

    Only trades opened with a score (short options with credit, risk and a live delta) carry an
    entry EV; ``with_expected`` says how many per group.
    """
    closed = await ctx.repo.closed_trades(ctx.user_id)
    rows = [{"layer": t.layer, "pnl": calculate_pnl(t), "expected": t.entry_ev} for t in closed]
    data = calibration(rows)
    data["note"] = (
        "Expected value is recorded at entry for short options with a credit, a risk amount and a "
        "live delta; other trades show realised results only."
    )
    return {"success": True, "data": data}
