"""Favorite toggle endpoints."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.db import get_db
from app.models import FavoriteUpscaleStatusResponse
from app.services.favorite_upscale_service import FavoriteUpscaleService
from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)

_DEFAULT_UPSCALE_MODEL = "remacri_original.safetensors"

router = APIRouter(prefix="/api/v1/generations", tags=["favorites"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_favorite_upscale_service(request: Request) -> FavoriteUpscaleService:
    service = getattr(request.app.state, "favorite_upscale_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Favorite upscale service is unavailable",
        )
    return service


@router.post("/{generation_id}/favorite")
async def toggle_favorite(generation_id: str, request: Request) -> dict[str, bool | str]:
    """Toggle favorite status for a generation.

    When a generation is marked as favorite and has not yet been upscaled,
    an upscale job is automatically queued in the background.
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, is_favorite, upscaled_image_path FROM generations WHERE id = ?",
            (generation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation {generation_id} not found",
            )

        already_upscaled = bool(row.get("upscaled_image_path"))
        new_is_favorite = 0 if bool(row.get("is_favorite")) else 1

        await db.execute(
            """UPDATE generations
               SET is_favorite = ?,
                   favorited_at = ?,
                   postprocess_kind = CASE
                       WHEN ? = 1 AND postprocess_kind = 'upscale' AND postprocess_status = 'failed'
                       THEN NULL ELSE postprocess_kind END,
                   postprocess_status = CASE
                       WHEN ? = 1 AND postprocess_kind = 'upscale' AND postprocess_status = 'failed'
                       THEN NULL ELSE postprocess_status END,
                   postprocess_message = CASE
                       WHEN ? = 1 AND postprocess_kind = 'upscale' AND postprocess_status = 'failed'
                       THEN NULL ELSE postprocess_message END
               WHERE id = ?""",
            (
                new_is_favorite,
                _now_iso() if new_is_favorite else None,
                new_is_favorite,
                new_is_favorite,
                new_is_favorite,
                generation_id,
            ),
        )

        cursor = await db.execute(
            "SELECT is_favorite FROM generations WHERE id = ?",
            (generation_id,),
        )
        row = await cursor.fetchone()
        await db.commit()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )

    is_favorite = bool(row.get("is_favorite", 0))

    # Auto-upscale when favorited and not yet upscaled
    if settings.AUTO_UPSCALE_FAVORITES and is_favorite and not already_upscaled:
        service: GenerationService = request.app.state.generation_service
        asyncio.create_task(
            _auto_upscale(generation_id, service),
            name=f"auto_upscale_{generation_id}",
        )

    return {
        "id": generation_id,
        "is_favorite": is_favorite,
    }


@router.post("/{generation_id}/ready")
async def toggle_ready_to_go(generation_id: str) -> dict[str, str | int | None]:
    """Toggle ready-to-go state for a generation using publish_approved=1/0."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, publish_approved FROM generations WHERE id = ?",
            (generation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation {generation_id} not found",
            )

        current = int(row.get("publish_approved") or 0)
        next_value = 0 if current == 1 else 1
        curated_at = _now_iso() if next_value == 1 else None

        await db.execute(
            "UPDATE generations SET publish_approved = ?, curated_at = ? WHERE id = ?",
            (next_value, curated_at, generation_id),
        )
        await db.commit()

    return {
        "id": generation_id,
        "publish_approved": next_value,
        "curated_at": curated_at,
    }


async def _auto_upscale(generation_id: str, service: GenerationService) -> None:
    """Fire-and-forget upscale triggered by favorite toggle."""
    try:
        await service.queue_upscale(
            generation_id=generation_id,
            upscale_model=_DEFAULT_UPSCALE_MODEL,
        )
        logger.info("Auto-upscale queued for favorite %s", generation_id)
    except Exception as exc:
        logger.warning("Auto-upscale failed for %s: %s", generation_id, exc)


@router.post("/favorites/upscale-backlog")
async def queue_favorite_upscale_backlog(request: Request) -> dict[str, object]:
    """Queue upscales for all current favorites that do not yet have results."""
    service = _get_favorite_upscale_service(request)
    return await service.queue_all_pending_favorites(source="manual-backlog")


@router.post("/favorites/upscale-daily/run")
async def run_daily_favorite_upscale(request: Request) -> dict[str, object]:
    """Manually execute the once-daily favorite upscale scan immediately."""
    service = _get_favorite_upscale_service(request)
    return await service.queue_all_pending_favorites(source="manual-daily")


@router.get("/favorites/upscale-status", response_model=FavoriteUpscaleStatusResponse)
async def get_favorite_upscale_status(request: Request) -> FavoriteUpscaleStatusResponse:
    service = _get_favorite_upscale_service(request)
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT
                COUNT(*) AS favorites_total,
                SUM(CASE WHEN upscaled_image_path IS NOT NULL THEN 1 ELSE 0 END) AS upscaled_done,
                SUM(CASE WHEN postprocess_status = 'queued' THEN 1 ELSE 0 END) AS queued,
                SUM(CASE WHEN postprocess_status = 'running' THEN 1 ELSE 0 END) AS running,
                SUM(
                    CASE WHEN upscaled_image_path IS NULL
                      AND (postprocess_status IS NULL OR postprocess_status NOT IN ('queued', 'running'))
                    THEN 1 ELSE 0 END
                ) AS daily_candidates
            FROM generations
            WHERE is_favorite = 1
            """
        )
        row = await cursor.fetchone()

    favorites_total = int((row or {}).get("favorites_total") or 0)
    upscaled_done = int((row or {}).get("upscaled_done") or 0)
    queued = int((row or {}).get("queued") or 0)
    running = int((row or {}).get("running") or 0)
    daily_candidates = int((row or {}).get("daily_candidates") or 0)
    pending = max(0, favorites_total - upscaled_done)
    completion_pct = round((upscaled_done / favorites_total) * 100, 1) if favorites_total else 0.0
    mode = settings.FAVORITE_UPSCALE_MODE if settings.FAVORITE_UPSCALE_MODE in {"safe", "quality"} else "safe"

    return FavoriteUpscaleStatusResponse(
        favorites_total=favorites_total,
        upscaled_done=upscaled_done,
        queued=queued,
        running=running,
        pending=pending,
        daily_candidates=daily_candidates,
        completion_pct=completion_pct,
        daily_enabled=settings.FAVORITE_UPSCALE_DAILY_ENABLED,
        daily_hour=settings.FAVORITE_UPSCALE_DAILY_HOUR,
        daily_minute=settings.FAVORITE_UPSCALE_DAILY_MINUTE,
        daily_batch_limit=None,
        backlog_window_start_hour=settings.FAVORITE_UPSCALE_BACKLOG_START_HOUR,
        backlog_window_end_hour=settings.FAVORITE_UPSCALE_BACKLOG_END_HOUR,
        backlog_window_open=service.is_backlog_window_open(),
        mode=mode,
    )
