"""Settings endpoints (FR-100–140) and first-login disclaimer acceptance."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Ctx, get_ctx
from app.domain import thresholds as th
from app.api.v1.schemas.settings import SettingsUpdate
from app.repositories.sql import InvalidInput

router = APIRouter()


@router.get("/thresholds")
async def threshold_info(ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    """Defaults, allowed ranges and the user's current values for every rule threshold."""
    settings = await ctx.repo.get_settings(ctx.user_id)
    return {
        "success": True,
        "data": {
            "defaults": th.DEFAULTS.to_dict(),
            "bounds": {k: {"min": lo, "max": hi} for k, (lo, hi) in th.BOUNDS.items()},
            "overrides": settings["thresholds"],
            "effective": settings["effective_thresholds"],
            "loosened": th.loosened(settings["thresholds"]),
        },
    }


@router.get("")
async def get_settings(ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    return {"success": True, "data": await ctx.repo.get_settings(ctx.user_id)}


@router.put("")
async def update_settings(payload: SettingsUpdate, ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    """Partial update: only the fields that are sent change. Changes are audit-logged."""
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    try:
        data = await ctx.repo.update_settings(ctx.user_id, changes)
    except InvalidInput as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    warnings = th.loosened(data["thresholds"]) if "thresholds" in changes else []
    return {"success": True, "data": data, "warnings": warnings}


@router.post("/disclaimer")
async def accept_disclaimer(ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    """Record that the user accepted the not-financial-advice disclaimer."""
    return {"success": True, "data": await ctx.repo.accept_disclaimer(ctx.user_id)}
