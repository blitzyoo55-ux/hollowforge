"""Background scheduler: preset-based batch generation at scheduled times."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db import get_db
from app.models import GenerationCreate, LoraInput
from app.services.generation_service import GenerationService

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
except ModuleNotFoundError:  # pragma: no cover - runtime dependency guard
    AsyncIOScheduler = None  # type: ignore[assignment]
    CronTrigger = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(raw: str | None, default: Any) -> Any:
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_or_default(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class SchedulerService:
    """Schedules and executes preset-based batch generation jobs."""

    def __init__(self, generation_service: GenerationService) -> None:
        self._gen_service = generation_service
        self._scheduler = AsyncIOScheduler() if AsyncIOScheduler else None

    @property
    def available(self) -> bool:
        return self._scheduler is not None

    async def start(self) -> None:
        """Load all enabled jobs from DB and start scheduler."""
        if self._scheduler is None:
            logger.warning(
                "APScheduler is not installed. Scheduler disabled. "
                "Install with: cd backend && .venv/bin/pip install \"apscheduler<4\""
            )
            return

        if not self._scheduler.running:
            self._scheduler.start()
        await self._reload_jobs()
        logger.info("Scheduler started with %d enabled job(s).", len(await self.list_jobs(enabled_only=True)))

    async def stop(self) -> None:
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def _reload_jobs(self) -> None:
        """Remove all jobs and re-register from DB."""
        if self._scheduler is None:
            return

        self._scheduler.remove_all_jobs()
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT *
                   FROM scheduled_jobs
                   WHERE enabled = 1
                   ORDER BY created_at ASC"""
            )
            rows = await cursor.fetchall()

        for row in rows:
            self._add_job(row)

    def _add_job(self, row: dict[str, Any]) -> None:
        if self._scheduler is None or CronTrigger is None:
            return

        self._scheduler.add_job(
            self._run_job,
            CronTrigger(hour=row["cron_hour"], minute=row["cron_minute"]),
            id=row["id"],
            args=[row["id"]],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )

    async def _run_job(self, job_id: str, force: bool = False) -> dict[str, Any]:
        """Execute a scheduled job: load preset and enqueue generation batch."""
        last_run_at = _now_iso()

        try:
            query = (
                "SELECT sj.*, "
                "p.checkpoint, p.loras, p.prompt_template, p.negative_prompt, p.default_params, p.tags "
                "FROM scheduled_jobs sj "
                "JOIN presets p ON sj.preset_id = p.id "
                "WHERE sj.id = ?"
            )
            params: tuple[Any, ...]
            if force:
                params = (job_id,)
            else:
                query += " AND sj.enabled = 1"
                params = (job_id,)

            async with get_db() as db:
                cursor = await db.execute(query, params)
                row = await cursor.fetchone()

            if row is None:
                status = (
                    f"error: job {job_id} not found"
                    if force
                    else f"error: job {job_id} disabled or not found"
                )
                return {"success": False, "queued": 0, "status": status}

            gen_create = self._build_generation(row)
            target_count = int(row["count"])
            queued = 0
            last_error: str | None = None

            for _ in range(target_count):
                try:
                    await self._gen_service.queue_generation(gen_create)
                    queued += 1
                except Exception as exc:  # pragma: no cover - runtime path
                    last_error = str(exc)
                    logger.exception(
                        "Scheduled job %s failed during queueing (%d/%d).",
                        job_id,
                        queued,
                        target_count,
                    )
                    break

            if last_error:
                status = f"error: queued {queued}/{target_count} ({last_error[:200]})"
                success = False
            else:
                status = f"success: queued {queued}/{target_count}"
                success = True

            await self._update_last_run(job_id, last_run_at, status)
            return {"success": success, "queued": queued, "status": status}
        except Exception as exc:  # pragma: no cover - runtime path
            status = f"error: {str(exc)[:280]}"
            logger.exception("Scheduled job %s execution failed.", job_id)
            await self._update_last_run(job_id, last_run_at, status)
            return {"success": False, "queued": 0, "status": status}

    async def add_or_update_job(self, job_data: dict[str, Any]) -> dict[str, Any]:
        """Create or update a scheduled job in DB and scheduler."""
        job_id = str(job_data.get("id") or "").strip() or str(uuid.uuid4())
        now = _now_iso()

        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM scheduled_jobs WHERE id = ?",
                (job_id,),
            )
            existing = await cursor.fetchone()

            if existing is None:
                if "id" in job_data and not {"name", "preset_id"} <= set(job_data):
                    raise LookupError(f"Scheduled job {job_id} not found")

                row = {
                    "id": job_id,
                    "name": job_data.get("name"),
                    "preset_id": job_data.get("preset_id"),
                    "count": job_data.get("count", 4),
                    "cron_hour": job_data.get("cron_hour", 2),
                    "cron_minute": job_data.get("cron_minute", 0),
                    "enabled": job_data.get("enabled", True),
                    "last_run_at": None,
                    "last_run_status": None,
                    "created_at": now,
                    "updated_at": now,
                }
                normalized = self._normalize_row_payload(row)
                await self._assert_preset_exists(db, normalized["preset_id"])
                await db.execute(
                    """INSERT INTO scheduled_jobs
                       (id, name, preset_id, count, cron_hour, cron_minute, enabled,
                        last_run_at, last_run_status, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        normalized["id"],
                        normalized["name"],
                        normalized["preset_id"],
                        normalized["count"],
                        normalized["cron_hour"],
                        normalized["cron_minute"],
                        normalized["enabled"],
                        None,
                        None,
                        normalized["created_at"],
                        normalized["updated_at"],
                    ),
                )
            else:
                row = dict(existing)
                for key in (
                    "name",
                    "preset_id",
                    "count",
                    "cron_hour",
                    "cron_minute",
                    "enabled",
                ):
                    if key in job_data and job_data[key] is not None:
                        row[key] = job_data[key]
                row["updated_at"] = now

                normalized = self._normalize_row_payload(row)
                await self._assert_preset_exists(db, normalized["preset_id"])
                await db.execute(
                    """UPDATE scheduled_jobs
                       SET name = ?, preset_id = ?, count = ?,
                           cron_hour = ?, cron_minute = ?, enabled = ?, updated_at = ?
                       WHERE id = ?""",
                    (
                        normalized["name"],
                        normalized["preset_id"],
                        normalized["count"],
                        normalized["cron_hour"],
                        normalized["cron_minute"],
                        normalized["enabled"],
                        normalized["updated_at"],
                        normalized["id"],
                    ),
                )

            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM scheduled_jobs WHERE id = ?",
                (job_id,),
            )
            saved = await cursor.fetchone()

        if saved is None:
            raise RuntimeError(f"Failed to persist scheduled job {job_id}")

        if self._scheduler is not None:
            if saved["enabled"]:
                self._add_job(saved)
            else:
                self._remove_job_from_scheduler(saved["id"])

        return self._row_to_response(saved)

    async def delete_job(self, job_id: str) -> bool:
        """Remove job from DB and scheduler."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM scheduled_jobs WHERE id = ?",
                (job_id,),
            )
            if await cursor.fetchone() is None:
                return False

            await db.execute("DELETE FROM scheduled_jobs WHERE id = ?", (job_id,))
            await db.commit()

        self._remove_job_from_scheduler(job_id)
        return True

    async def list_jobs(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """Return all scheduled jobs from DB."""
        query = "SELECT * FROM scheduled_jobs"
        params: tuple[Any, ...] = ()
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"

        async with get_db() as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()

        return [self._row_to_response(row) for row in rows]

    async def run_now(self, job_id: str) -> dict[str, Any]:
        """Execute job immediately regardless of enabled state."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id FROM scheduled_jobs WHERE id = ?",
                (job_id,),
            )
            if await cursor.fetchone() is None:
                raise LookupError(f"Scheduled job {job_id} not found")
        return await self._run_job(job_id, force=True)

    async def _assert_preset_exists(self, db: Any, preset_id: str) -> None:
        cursor = await db.execute("SELECT id FROM presets WHERE id = ?", (preset_id,))
        if await cursor.fetchone() is None:
            raise ValueError(f"Preset {preset_id} not found")

    async def _update_last_run(
        self, job_id: str, last_run_at: str, status: str
    ) -> None:
        async with get_db() as db:
            await db.execute(
                """UPDATE scheduled_jobs
                   SET last_run_at = ?, last_run_status = ?, updated_at = ?
                   WHERE id = ?""",
                (last_run_at, status, _now_iso(), job_id),
            )
            await db.commit()

    def _build_generation(self, row: dict[str, Any]) -> GenerationCreate:
        default_params = _parse_json(row.get("default_params"), {})
        lora_raw = _parse_json(row.get("loras"), [])
        tags_raw = _parse_json(row.get("tags"), None)
        loras: list[LoraInput] = []

        for lora in lora_raw:
            if not isinstance(lora, dict):
                continue
            try:
                loras.append(LoraInput(**lora))
            except Exception:
                logger.warning("Skipping invalid LoRA payload in preset %s", row["preset_id"])

        tags: list[str] | None = None
        if isinstance(tags_raw, list):
            tags = [str(tag) for tag in tags_raw if str(tag).strip()]

        clip_skip = _optional_int(default_params.get("clip_skip"))
        seed = _optional_int(default_params.get("seed"))

        return GenerationCreate(
            prompt=row.get("prompt_template") or "",
            negative_prompt=row.get("negative_prompt"),
            checkpoint=row["checkpoint"],
            loras=loras,
            seed=seed,
            steps=_int_or_default(default_params.get("steps"), 28),
            cfg=_float_or_default(default_params.get("cfg"), 7.0),
            width=_int_or_default(default_params.get("width"), 832),
            height=_int_or_default(default_params.get("height"), 1216),
            sampler=str(default_params.get("sampler") or "euler"),
            scheduler=str(default_params.get("scheduler") or "normal"),
            clip_skip=clip_skip,
            tags=tags,
            preset_id=row["preset_id"],
            source_id=f"scheduler:{row['id']}",
        )

    def _remove_job_from_scheduler(self, job_id: str) -> None:
        if self._scheduler is None:
            return
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

    def _row_to_response(self, row: dict[str, Any]) -> dict[str, Any]:
        next_run_at: str | None = None
        if self._scheduler is not None:
            scheduled_job = self._scheduler.get_job(row["id"])
            if scheduled_job and scheduled_job.next_run_time:
                next_run_at = scheduled_job.next_run_time.isoformat()

        return {
            "id": row["id"],
            "name": row["name"],
            "preset_id": row["preset_id"],
            "count": int(row["count"]),
            "cron_hour": int(row["cron_hour"]),
            "cron_minute": int(row["cron_minute"]),
            "enabled": bool(row["enabled"]),
            "last_run_at": row.get("last_run_at"),
            "last_run_status": row.get("last_run_status"),
            "next_run_at": next_run_at,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _normalize_row_payload(self, row: dict[str, Any]) -> dict[str, Any]:
        name = str(row.get("name") or "").strip()
        if not name:
            raise ValueError("name is required")
        if len(name) > 120:
            raise ValueError("name must be <= 120 characters")

        preset_id = str(row.get("preset_id") or "").strip()
        if not preset_id:
            raise ValueError("preset_id is required")

        count = int(row.get("count", 4))
        if count < 1 or count > 24:
            raise ValueError("count must be between 1 and 24")

        cron_hour = int(row.get("cron_hour", 2))
        if cron_hour < 0 or cron_hour > 23:
            raise ValueError("cron_hour must be between 0 and 23")

        cron_minute = int(row.get("cron_minute", 0))
        if cron_minute < 0 or cron_minute > 59:
            raise ValueError("cron_minute must be between 0 and 59")

        enabled = 1 if bool(row.get("enabled", True)) else 0

        return {
            "id": str(row["id"]),
            "name": name,
            "preset_id": preset_id,
            "count": count,
            "cron_hour": cron_hour,
            "cron_minute": cron_minute,
            "enabled": enabled,
            "created_at": row.get("created_at") or _now_iso(),
            "updated_at": row.get("updated_at") or _now_iso(),
        }
