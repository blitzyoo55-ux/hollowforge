"""Daily batching for favorite image upscales."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from app.config import settings
from app.db import get_db
from app.services.generation_service import GenerationService

logger = logging.getLogger(__name__)

_ACTIVE_POSTPROCESS_STATES = {"queued", "running"}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _seconds_until_next_run(hour: int, minute: int) -> float:
    now = datetime.now().astimezone()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


class FavoriteUpscaleService:
    """Queues favorite-image upscales in one-off and daily batch modes."""

    def __init__(self, generation_service: GenerationService) -> None:
        self._gen_service = generation_service
        self._loop_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if not settings.FAVORITE_UPSCALE_DAILY_ENABLED:
            logger.info("Favorite daily upscale scheduler disabled by config.")
            return
        if self._loop_task and not self._loop_task.done():
            return
        self._loop_task = asyncio.create_task(
            self._daily_loop(),
            name="favorite_upscale_daily_loop",
        )
        logger.info(
            "Favorite daily upscale scheduler enabled at %02d:%02d.",
            settings.FAVORITE_UPSCALE_DAILY_HOUR,
            settings.FAVORITE_UPSCALE_DAILY_MINUTE,
        )

    async def stop(self) -> None:
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            pass
        self._loop_task = None

    def is_backlog_window_open(self) -> bool:
        return self._gen_service._is_backlog_window_open()

    async def queue_all_pending_favorites(self, *, source: str = "manual") -> dict[str, Any]:
        """Queue every favorited image that still needs an upscale."""
        return await self._queue_pending_favorites(only_new=False, source=source)

    async def queue_new_favorites(self, *, source: str = "daily") -> dict[str, Any]:
        """Queue only newly favorited images that have not been queued since favorite time."""
        return await self._queue_pending_favorites(
            only_new=True,
            source=source,
            limit=max(1, settings.FAVORITE_UPSCALE_DAILY_BATCH_LIMIT),
        )

    async def _daily_loop(self) -> None:
        while True:
            delay = _seconds_until_next_run(
                settings.FAVORITE_UPSCALE_DAILY_HOUR,
                settings.FAVORITE_UPSCALE_DAILY_MINUTE,
            )
            logger.info("Favorite daily upscale next run in %.0f seconds.", delay)
            await asyncio.sleep(delay)
            try:
                summary = await self.queue_all_pending_favorites(source="daily")
                logger.info(
                    "Favorite daily upscale completed: queued=%d skipped=%d candidates=%d",
                    summary["queued"],
                    summary["skipped"],
                    summary["candidates"],
                )
            except Exception:
                logger.exception("Favorite daily upscale batch failed.")

    async def _queue_pending_favorites(
        self,
        *,
        only_new: bool,
        source: str,
        limit: int | None = None,
    ) -> dict[str, Any]:
        rows = await self._fetch_pending_favorites(only_new=only_new, limit=limit)
        queued = 0
        skipped = 0
        skipped_reasons: dict[str, int] = {}
        mode = settings.FAVORITE_UPSCALE_MODE

        for row in rows:
            gen_id = str(row["id"])
            try:
                await self._gen_service.queue_upscale(
                    generation_id=gen_id,
                    upscale_model="auto",
                    mode=mode if mode in {"safe", "quality"} else "safe",
                    queue_class="favorite_backlog",
                )
                await self._mark_queued(gen_id)
                queued += 1
            except Exception as exc:
                skipped += 1
                reason = str(exc).split("\n", 1)[0][:160]
                skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
                logger.info(
                    "Favorite upscale skipped for %s (%s, source=%s): %s",
                    gen_id,
                    row.get("checkpoint"),
                    source,
                    reason,
                )

        return {
            "source": source,
            "only_new": only_new,
            "mode": mode if mode in {"safe", "quality"} else "safe",
            "candidates": len(rows),
            "limit": limit,
            "queued": queued,
            "skipped": skipped,
            "skipped_reasons": skipped_reasons,
            "ran_at": _now_iso(),
        }

    async def _fetch_pending_favorites(
        self,
        *,
        only_new: bool,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = [
            "is_favorite = 1",
            "status = 'completed'",
            "image_path IS NOT NULL",
            "upscaled_image_path IS NULL",
            "(postprocess_status IS NULL OR postprocess_status NOT IN ('queued', 'running'))",
        ]
        if only_new:
            conditions.append(
                "("
                "favorite_upscale_queued_at IS NULL "
                "OR (favorited_at IS NOT NULL AND favorite_upscale_queued_at < favorited_at) "
                "OR postprocess_status = 'failed'"
                ")"
            )

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT id, checkpoint, favorited_at, favorite_upscale_queued_at, postprocess_status
            FROM generations
            WHERE {where_clause}
            ORDER BY COALESCE(favorited_at, created_at) ASC, created_at ASC
        """
        if limit is not None and limit > 0:
            query += f"\nLIMIT {int(limit)}"
        async with get_db() as db:
            cursor = await db.execute(query)
            return await cursor.fetchall()

    async def _mark_queued(self, generation_id: str) -> None:
        async with get_db() as db:
            await db.execute(
                "UPDATE generations SET favorite_upscale_queued_at = ? WHERE id = ?",
                (_now_iso(), generation_id),
            )
            await db.commit()
