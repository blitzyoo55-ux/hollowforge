"""Generation queue and background worker."""

from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from PIL import Image

from app.config import settings
from app.db import get_db
from app.models import GenerationCreate, GenerationResponse, GenerationStatus, LoraInput
from app.services import adetailer_service
from app.services.comfyui_client import ComfyUIClient, ComfyUIWaitCancelledError
from app.services.image_service import (
    save_generation_image,
    save_upscaled_preview,
    save_workflow,
)
from app.services.model_compatibility import is_checkpoint_compatible
from app.services.safe_upscale_runner import run_safe_upscale
from app.services.upscaler import (
    recommend_upscale_model,
    resolve_upscale_model_path,
)

# Map user-facing sampler aliases → ComfyUI canonical names
_SAMPLER_ALIASES: dict[str, str] = {
    "euler_a": "euler_ancestral",
    "euler_ancestral": "euler_ancestral",
    "dpmpp_2m_sde": "dpmpp_2m_sde",
    "dpmpp_2m": "dpmpp_2m",
    "euler": "euler",
    "ddim": "ddim",
}


def _normalize_sampler(sampler: str) -> str:
    return _SAMPLER_ALIASES.get(sampler, sampler)
from app.services.watermark_service import apply_watermark
from app.services.workflow_builder import (
    build_hiresfix_workflow,
    build_quality_upscale_workflow,
    build_upscale_workflow,
    build_workflow,
    compute_quality_redraw_dimensions,
    QUALITY_UPSCALE_REQUIRED_NODES,
)

logger = logging.getLogger(__name__)
_MAX_SEED = 2**31 - 1
_ACTIVE_POSTPROCESS_STATES = {"queued", "running"}
_DEFAULT_WATERMARK_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "text": "Lab-XX",
    "position": "bottom-right",
    "opacity": 0.6,
    "font_size": 36,
    "padding": 20,
    "color": "#FFFFFF",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _apply_default_negative_prompt(gen: GenerationCreate) -> GenerationCreate:
    if gen.preserve_blank_negative_prompt:
        return gen.model_copy(update={"negative_prompt": None})
    if isinstance(gen.negative_prompt, str) and gen.negative_prompt.strip():
        return gen
    return gen.model_copy(update={"negative_prompt": settings.DEFAULT_NEGATIVE_PROMPT})


def _row_to_response(row: dict[str, Any]) -> GenerationResponse:
    """Convert a raw DB row dict into a GenerationResponse."""
    loras_raw = _parse_json(row.get("loras"), [])
    loras = [LoraInput(**l) if isinstance(l, dict) else l for l in loras_raw]
    tags = _parse_json(row.get("tags"))
    return GenerationResponse(
        id=row["id"],
        prompt=row["prompt"],
        negative_prompt=row.get("negative_prompt"),
        checkpoint=row["checkpoint"],
        loras=loras,
        seed=row["seed"],
        steps=row["steps"],
        cfg=row["cfg"],
        width=row["width"],
        height=row["height"],
        sampler=_normalize_sampler(row["sampler"]),
        scheduler=row["scheduler"],
        clip_skip=row.get("clip_skip"),
        status=row["status"],
        image_path=row.get("image_path"),
        watermarked_path=row.get("watermarked_path"),
        upscaled_image_path=row.get("upscaled_image_path"),
        adetailed_path=row.get("adetailed_path"),
        hiresfix_path=row.get("hiresfix_path"),
        dreamactor_path=row.get("dreamactor_path"),
        dreamactor_task_id=row.get("dreamactor_task_id"),
        dreamactor_status=row.get("dreamactor_status"),
        upscaled_preview_path=row.get("upscaled_preview_path"),
        upscale_model=row.get("upscale_model"),
        thumbnail_path=row.get("thumbnail_path"),
        workflow_path=row.get("workflow_path"),
        generation_time_sec=row.get("generation_time_sec"),
        tags=tags,
        preset_id=row.get("preset_id"),
        notes=row.get("notes"),
        source_id=row.get("source_id"),
        comfyui_prompt_id=row.get("comfyui_prompt_id"),
        error_message=row.get("error_message"),
        postprocess_kind=row.get("postprocess_kind"),
        postprocess_status=row.get("postprocess_status"),
        postprocess_message=row.get("postprocess_message"),
        is_favorite=bool(row.get("is_favorite", 0)),
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
    )


@dataclass
class _QueueJob:
    kind: Literal["generation", "upscale", "adetail", "hiresfix"]
    generation_id: str
    queue_class: Literal["generation", "interactive", "favorite_backlog"] = "interactive"
    upscale_model: str | None = None
    upscale_mode: Literal["safe", "quality"] = "safe"
    upscale_factor: float = 1.5
    denoise: float = 0.35
    steps: int = 20
    cfg: float = 7.0
    result_future: asyncio.Future[GenerationResponse] | None = None


class GenerationService:
    """Manages the generation queue and background processing worker."""

    def __init__(self, client: ComfyUIClient | None = None) -> None:
        self._generation_queue: asyncio.Queue[_QueueJob] = asyncio.Queue()
        self._interactive_queue: asyncio.Queue[_QueueJob] = asyncio.Queue()
        self._favorite_backlog_queue: asyncio.Queue[_QueueJob] = asyncio.Queue()
        self._queue_event = asyncio.Event()
        self._cancel_events: dict[str, asyncio.Event] = {}
        self._client = client or ComfyUIClient()
        self._owns_client = client is None
        self._worker_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_worker(self) -> None:
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def cleanup_stale(self) -> int:
        """Mark stale queued/running generations as failed on startup."""
        async with get_db() as db:
            generation_cursor = await db.execute(
                """UPDATE generations
                   SET status = 'failed',
                       error_message = 'Server restarted',
                       completed_at = ?
                   WHERE status IN ('queued', 'running')""",
                (_now_iso(),),
            )
            postprocess_cursor = await db.execute(
                """UPDATE generations
                   SET postprocess_status = 'failed',
                       postprocess_message = 'Server restarted',
                       error_message = 'Server restarted'
                   WHERE postprocess_status IN ('queued', 'running')""",
            )
            await db.commit()
            return generation_cursor.rowcount + postprocess_cursor.rowcount

    async def shutdown(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._owns_client:
            await self._client.close()

    def _is_backlog_window_open(self) -> bool:
        start = settings.FAVORITE_UPSCALE_BACKLOG_START_HOUR
        end = settings.FAVORITE_UPSCALE_BACKLOG_END_HOUR
        now_hour = datetime.now().astimezone().hour
        if start == end:
            return True
        if start < end:
            return start <= now_hour < end
        return now_hour >= start or now_hour < end

    def _enqueue_job(self, job: _QueueJob) -> None:
        if job.queue_class == "generation":
            self._generation_queue.put_nowait(job)
        elif job.queue_class == "favorite_backlog":
            self._favorite_backlog_queue.put_nowait(job)
        else:
            self._interactive_queue.put_nowait(job)
        self._queue_event.set()

    def _next_job_nowait(self) -> _QueueJob | None:
        if not self._generation_queue.empty():
            return self._generation_queue.get_nowait()
        if not self._interactive_queue.empty():
            return self._interactive_queue.get_nowait()
        if self._is_backlog_window_open() and not self._favorite_backlog_queue.empty():
            return self._favorite_backlog_queue.get_nowait()
        return None

    async def _dequeue_next_job(self) -> _QueueJob:
        while True:
            job = self._next_job_nowait()
            if job is not None:
                return job

            self._queue_event.clear()
            job = self._next_job_nowait()
            if job is not None:
                self._queue_event.set()
                return job

            if (not self._favorite_backlog_queue.empty()) and not self._is_backlog_window_open():
                try:
                    await asyncio.wait_for(self._queue_event.wait(), timeout=15.0)
                except asyncio.TimeoutError:
                    pass
                continue

            await self._queue_event.wait()

    async def _get_generation_row(self, gen_id: str) -> dict[str, Any] | None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?",
                (gen_id,),
            )
            return await cursor.fetchone()

    def _get_cancel_event(self, gen_id: str) -> asyncio.Event:
        event = self._cancel_events.get(gen_id)
        if event is None:
            event = asyncio.Event()
            self._cancel_events[gen_id] = event
        return event

    async def _mark_generation_cancelled(self, gen_id: str) -> None:
        async with get_db() as db:
            await db.execute(
                """UPDATE generations
                   SET status = 'cancelled',
                       completed_at = COALESCE(completed_at, ?)
                   WHERE id = ?
                     AND status NOT IN ('completed', 'failed', 'cancelled')""",
                (_now_iso(), gen_id),
            )
            await db.commit()

    async def _set_postprocess_state(
        self,
        gen_id: str,
        kind: str | None,
        status: str | None,
        message: str | None = None,
        *,
        clear_error: bool = False,
    ) -> GenerationResponse:
        async with get_db() as db:
            if clear_error:
                await db.execute(
                    """UPDATE generations
                       SET postprocess_kind = ?,
                           postprocess_status = ?,
                           postprocess_message = ?,
                           error_message = NULL
                       WHERE id = ?""",
                    (kind, status, message, gen_id),
                )
            else:
                await db.execute(
                    """UPDATE generations
                       SET postprocess_kind = ?,
                           postprocess_status = ?,
                           postprocess_message = ?
                       WHERE id = ?""",
                    (kind, status, message, gen_id),
                )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?",
                (gen_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            raise RuntimeError(f"Generation {gen_id} disappeared during postprocess update")
        return _row_to_response(row)

    async def _queue_postprocess_job(
        self,
        *,
        generation_id: str,
        kind: Literal["upscale", "adetail", "hiresfix"],
        message: str,
        job: _QueueJob,
    ) -> GenerationResponse:
        row = await self._get_generation_row(generation_id)
        if row is None:
            raise ValueError(f"Generation {generation_id} not found")
        if row["status"] != "completed":
            raise ValueError(f"Only completed generations can run {kind}")

        active_status = row.get("postprocess_status")
        active_kind = row.get("postprocess_kind")
        if active_status in _ACTIVE_POSTPROCESS_STATES:
            raise ValueError(
                f"{active_kind or 'Another postprocess'} is already {active_status} for this generation"
            )

        queued = await self._set_postprocess_state(
            generation_id,
            kind,
            "queued",
            message,
            clear_error=True,
        )
        self._enqueue_job(job)
        return queued

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def queue_generation(self, gen: GenerationCreate) -> GenerationResponse:
        """Insert a new generation record and enqueue it for processing."""
        gen = _apply_default_negative_prompt(gen)
        await self._validate_lora_compatibility(gen)
        seed = gen.resolved_seed()
        return await self._insert_generation_record(gen, seed)

    async def create_generation_shell(
        self,
        gen: GenerationCreate,
    ) -> GenerationResponse:
        """Insert a queued generation row without enqueuing local worker work."""
        gen = _apply_default_negative_prompt(gen)
        await self._validate_lora_compatibility(gen)
        seed = gen.resolved_seed()
        return await self._insert_generation_record(gen, seed, enqueue=False)

    async def queue_generation_batch(
        self,
        gen: GenerationCreate,
        count: int,
        seed_increment: int = 1,
    ) -> tuple[int, list[GenerationResponse]]:
        """Queue N generations with auto-incremented seeds.

        This is the reusable batch entry point for higher-level orchestration
        such as sequence shot candidate generation. Callers should reuse this
        method instead of duplicating seed-span or enqueue logic elsewhere.
        """
        gen = _apply_default_negative_prompt(gen)
        await self._validate_lora_compatibility(gen)
        if count < 2:
            raise ValueError("count must be >= 2 for batch generation")
        if seed_increment < 1:
            raise ValueError("seed_increment must be >= 1")
        if gen.source_id:
            existing_batch = await self._load_generations_by_source_id(gen.source_id)
            if existing_batch:
                if len(existing_batch) == count:
                    return existing_batch[0].seed, existing_batch
                if len(existing_batch) < count:
                    raise ValueError(
                        f"partial batch exists for source_id '{gen.source_id}': "
                        f"expected {count}, found {len(existing_batch)}"
                    )
                raise ValueError(
                    f"source_id '{gen.source_id}' already has {len(existing_batch)} "
                    f"generations; expected {count}"
                )

        span = (count - 1) * seed_increment
        if span > _MAX_SEED:
            raise ValueError("Batch size and seed increment exceed valid seed range")

        if gen.seed is None or gen.seed == -1:
            base_seed = random.randint(0, _MAX_SEED - span)
        else:
            base_seed = gen.seed
            if base_seed + span > _MAX_SEED:
                raise ValueError(
                    f"base seed {base_seed} with count={count} and seed_increment="
                    f"{seed_increment} exceeds max seed {_MAX_SEED}"
                )

        queued: list[GenerationResponse] = []
        for i in range(count):
            seed = base_seed + (i * seed_increment)
            queued.append(await self._insert_generation_record(gen, seed))

        return base_seed, queued

    async def create_generation_shell_batch(
        self,
        gen: GenerationCreate,
        count: int,
        seed_increment: int = 1,
    ) -> tuple[int, list[GenerationResponse]]:
        """Insert queued generation lineage shells without local worker enqueue."""
        gen = _apply_default_negative_prompt(gen)
        await self._validate_lora_compatibility(gen)
        if count < 2:
            raise ValueError("count must be >= 2 for batch generation")
        if seed_increment < 1:
            raise ValueError("seed_increment must be >= 1")
        if gen.source_id:
            existing_batch = await self._load_generations_by_source_id(gen.source_id)
            if existing_batch:
                if len(existing_batch) == count:
                    return existing_batch[0].seed, existing_batch
                if len(existing_batch) < count:
                    raise ValueError(
                        f"partial batch exists for source_id '{gen.source_id}': "
                        f"expected {count}, found {len(existing_batch)}"
                    )
                raise ValueError(
                    f"source_id '{gen.source_id}' already has {len(existing_batch)} "
                    f"generations; expected {count}"
                )

        span = (count - 1) * seed_increment
        if span > _MAX_SEED:
            raise ValueError("Batch size and seed increment exceed valid seed range")

        if gen.seed is None or gen.seed == -1:
            base_seed = random.randint(0, _MAX_SEED - span)
        else:
            base_seed = gen.seed
            if base_seed + span > _MAX_SEED:
                raise ValueError(
                    f"base seed {base_seed} with count={count} and seed_increment="
                    f"{seed_increment} exceeds max seed {_MAX_SEED}"
                )

        queued: list[GenerationResponse] = []
        for i in range(count):
            seed = base_seed + (i * seed_increment)
            queued.append(
                await self._insert_generation_record(gen, seed, enqueue=False)
            )

        return base_seed, queued

    async def _load_generations_by_source_id(
        self,
        source_id: str,
    ) -> list[GenerationResponse]:
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT * FROM generations
                   WHERE source_id = ?
                   ORDER BY seed ASC, created_at ASC, id ASC""",
                (source_id,),
            )
            rows = await cursor.fetchall()
        return [_row_to_response(row) for row in rows]

    async def _insert_generation_record(
        self,
        gen: GenerationCreate,
        seed: int,
        *,
        enqueue: bool = True,
    ) -> GenerationResponse:
        gen_id = str(uuid.uuid4())
        now = _now_iso()

        loras_json = json.dumps([l.model_dump() for l in gen.loras])
        tags_json = json.dumps(gen.tags) if gen.tags else None

        async with get_db() as db:
            await db.execute(
                """INSERT INTO generations
                   (id, prompt, negative_prompt, checkpoint, loras, seed,
                    steps, cfg, width, height, sampler, scheduler,
                    clip_skip, status, tags, preset_id, notes, source_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    gen_id,
                    gen.prompt,
                    gen.negative_prompt,
                    gen.checkpoint,
                    loras_json,
                    seed,
                    gen.steps,
                    gen.cfg,
                    gen.width,
                    gen.height,
                    gen.sampler,
                    gen.scheduler,
                    gen.clip_skip,
                    "queued",
                    tags_json,
                    gen.preset_id,
                    gen.notes,
                    gen.source_id,
                    now,
                ),
            )
            await db.commit()

            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            )
            row = await cursor.fetchone()

        if enqueue:
            self._enqueue_job(
                _QueueJob(
                    kind="generation",
                    generation_id=gen_id,
                    queue_class="generation",
                )
            )
        return _row_to_response(row)

    async def _validate_lora_compatibility(self, gen: GenerationCreate) -> None:
        """Reject known incompatible LoRA/checkpoint combinations early."""
        if not gen.loras:
            return

        filenames = sorted({l.filename for l in gen.loras})
        placeholders = ",".join("?" for _ in filenames)
        async with get_db() as db:
            cursor = await db.execute(
                f"SELECT filename, compatible_checkpoints FROM lora_profiles WHERE filename IN ({placeholders})",
                filenames,
            )
            rows = await cursor.fetchall()

        profile_by_filename = {row["filename"]: row for row in rows}
        incompatible: list[str] = []
        for lora in gen.loras:
            profile = profile_by_filename.get(lora.filename)
            if profile is None:
                # Unregistered LoRA: allow and let ComfyUI resolve it.
                continue
            if not is_checkpoint_compatible(
                profile.get("compatible_checkpoints"), gen.checkpoint
            ):
                incompatible.append(lora.filename)

        if incompatible:
            uniq = sorted(set(incompatible))
            raise ValueError(
                "Incompatible LoRA(s) for checkpoint "
                f"'{gen.checkpoint}': {', '.join(uniq)}"
            )

    async def queue_upscale(
        self,
        generation_id: str,
        upscale_model: str,
        mode: Literal["safe", "quality"] = "safe",
        denoise: float = 0.35,
        steps: int = 20,
        queue_class: Literal["interactive", "favorite_backlog"] = "interactive",
    ) -> GenerationResponse:
        """Queue an upscale job on the shared worker and return immediately."""
        if not 0.0 <= denoise <= 1.0:
            raise ValueError("denoise must be between 0.0 and 1.0")
        if steps < 1:
            raise ValueError("steps must be >= 1")
        if mode == "quality" and not settings.UPSCALE_QUALITY_ENABLED:
            raise ValueError(
                "Quality upscale is temporarily disabled while artifact issues are under investigation"
            )

        model_label = upscale_model or "auto"

        return await self._queue_postprocess_job(
            generation_id=generation_id,
            kind="upscale",
            message=f"Queued {mode} upscale with {model_label}",
            job=_QueueJob(
                kind="upscale",
                generation_id=generation_id,
                queue_class=queue_class,
                upscale_model=model_label,
                upscale_mode=mode,
                denoise=denoise,
                steps=steps,
            ),
        )

    async def queue_adetail(
        self,
        generation_id: str,
        denoise: float = 0.4,
        steps: int = 20,
    ) -> GenerationResponse:
        """Queue a face inpaint detail job and return immediately."""
        if not 0.05 <= denoise <= 0.9:
            raise ValueError("denoise must be between 0.05 and 0.9")
        if steps < 1:
            raise ValueError("steps must be >= 1")

        return await self._queue_postprocess_job(
            generation_id=generation_id,
            kind="adetail",
            message="Queued face detail refinement",
            job=_QueueJob(
                kind="adetail",
                generation_id=generation_id,
                denoise=denoise,
                steps=steps,
            ),
        )

    async def queue_hiresfix(
        self,
        generation_id: str,
        upscale_factor: float = 1.5,
        denoise: float = 0.5,
        steps: int = 20,
        cfg: float = 7.0,
    ) -> GenerationResponse:
        """Queue a latent upscale + second-pass sampler job and return immediately."""
        if not 1.1 <= upscale_factor <= 2.0:
            raise ValueError("upscale_factor must be between 1.1 and 2.0")
        if not 0.2 <= denoise <= 0.85:
            raise ValueError("denoise must be between 0.2 and 0.85")
        if steps < 1:
            raise ValueError("steps must be >= 1")
        if not 1.0 <= cfg <= 30.0:
            raise ValueError("cfg must be between 1.0 and 30.0")

        return await self._queue_postprocess_job(
            generation_id=generation_id,
            kind="hiresfix",
            message=f"Queued hiresfix at {upscale_factor:.2f}x",
            job=_QueueJob(
                kind="hiresfix",
                generation_id=generation_id,
                upscale_factor=upscale_factor,
                denoise=denoise,
                steps=steps,
                cfg=cfg,
            ),
        )

    async def apply_watermark_to_generation(self, gen_id: str) -> GenerationResponse:
        """Apply watermark settings to an existing completed generation."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            )
            row = await cursor.fetchone()

        if row is None:
            raise LookupError(f"Generation {gen_id} not found")
        if row["status"] != "completed":
            raise ValueError("Only completed generations can be watermarked")

        image_path = row.get("image_path")
        if not image_path:
            raise ValueError("Generation has no image_path")

        settings = await self._load_watermark_settings()
        watermarked_path = await asyncio.to_thread(
            apply_watermark,
            image_path,
            settings,
        )

        async with get_db() as db:
            await db.execute(
                "UPDATE generations SET watermarked_path = ? WHERE id = ?",
                (watermarked_path, gen_id),
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            )
            updated = await cursor.fetchone()

        if updated is None:
            raise RuntimeError(f"Generation {gen_id} disappeared after watermark")
        return _row_to_response(updated)

    async def get_generation(self, gen_id: str) -> GenerationResponse | None:
        row = await self._get_generation_row(gen_id)
        if row is None:
            return None
        return _row_to_response(row)

    async def get_generation_status(self, gen_id: str) -> GenerationStatus | None:
        async with get_db() as db:
            cursor = await db.execute(
                """SELECT id, status, generation_time_sec, steps,
                          postprocess_kind, postprocess_status
                   FROM generations WHERE id = ?""",
                (gen_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            estimated_time_sec = None
            steps = row.get("steps")

            if steps is not None:
                steps_cursor = await db.execute(
                    """SELECT AVG(generation_time_sec) AS avg_time, COUNT(*) AS cnt
                       FROM generations
                       WHERE status = 'completed'
                         AND generation_time_sec IS NOT NULL
                         AND steps = ?""",
                    (steps,),
                )
                steps_row = await steps_cursor.fetchone()
                if steps_row and steps_row.get("cnt", 0) >= 3:
                    estimated_time_sec = steps_row.get("avg_time")

            if estimated_time_sec is None:
                overall_cursor = await db.execute(
                    """SELECT AVG(generation_time_sec) AS avg_time
                       FROM generations
                       WHERE status = 'completed'
                         AND generation_time_sec IS NOT NULL"""
                )
                overall_row = await overall_cursor.fetchone()
                estimated_time_sec = overall_row.get("avg_time") if overall_row else None

        return GenerationStatus(
            id=row["id"],
            status=row["status"],
            generation_time_sec=row.get("generation_time_sec"),
            estimated_time_sec=estimated_time_sec,
            postprocess_kind=row.get("postprocess_kind"),
            postprocess_status=row.get("postprocess_status"),
        )

    async def cancel_generation(self, gen_id: str) -> bool:
        cancel_event = self._get_cancel_event(gen_id)
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, status, comfyui_prompt_id FROM generations WHERE id = ?",
                (gen_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return False

            if row["status"] in ("completed", "failed", "cancelled"):
                return False

            cancel_event.set()

            # Try to cancel in ComfyUI if running
            if row["status"] == "running" and row.get("comfyui_prompt_id"):
                await self._client.cancel_prompt(row["comfyui_prompt_id"])

            await db.execute(
                "UPDATE generations SET status = ?, completed_at = ? WHERE id = ?",
                ("cancelled", _now_iso(), gen_id),
            )
            await db.commit()
        return True

    async def _load_watermark_settings(self) -> dict[str, Any]:
        """Load watermark settings with safe defaults."""
        try:
            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT * FROM watermark_settings WHERE id = 1"
                )
                row = await cursor.fetchone()
        except Exception:
            logger.exception("Failed to load watermark settings from DB")
            return dict(_DEFAULT_WATERMARK_SETTINGS)

        if row is None:
            return dict(_DEFAULT_WATERMARK_SETTINGS)

        return {
            "enabled": bool(row.get("enabled", 0)),
            "text": row.get("text") or _DEFAULT_WATERMARK_SETTINGS["text"],
            "position": row.get("position")
            or _DEFAULT_WATERMARK_SETTINGS["position"],
            "opacity": row.get("opacity")
            if row.get("opacity") is not None
            else _DEFAULT_WATERMARK_SETTINGS["opacity"],
            "font_size": row.get("font_size")
            if row.get("font_size") is not None
            else _DEFAULT_WATERMARK_SETTINGS["font_size"],
            "padding": row.get("padding")
            if row.get("padding") is not None
            else _DEFAULT_WATERMARK_SETTINGS["padding"],
            "color": row.get("color") or _DEFAULT_WATERMARK_SETTINGS["color"],
        }

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        """Process queue jobs one at a time."""
        while True:
            job = await self._dequeue_next_job()
            try:
                if job.kind == "generation":
                    await self._process_generation(job.generation_id)
                elif job.kind == "upscale":
                    result = await self._process_upscale(
                        job.generation_id,
                        job.upscale_model or "remacri_original.safetensors",
                        mode=job.upscale_mode,
                        denoise=job.denoise,
                        steps=job.steps,
                    )
                    if job.result_future and not job.result_future.done():
                        job.result_future.set_result(result)
                elif job.kind == "adetail":
                    result = await self._process_adetail(
                        job.generation_id,
                        denoise=job.denoise,
                        steps=job.steps,
                    )
                    if job.result_future and not job.result_future.done():
                        job.result_future.set_result(result)
                elif job.kind == "hiresfix":
                    result = await self._process_hiresfix(
                        job.generation_id,
                        upscale_factor=job.upscale_factor,
                        denoise=job.denoise,
                        steps=job.steps,
                        cfg=job.cfg,
                    )
                    if job.result_future and not job.result_future.done():
                        job.result_future.set_result(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if (
                    job.kind in ("upscale", "adetail", "hiresfix")
                    and job.result_future
                    and not job.result_future.done()
                ):
                    job.result_future.set_exception(exc)
                else:
                    logger.exception(
                        "Unhandled error processing %s job for generation %s",
                        job.kind,
                        job.generation_id,
                    )
            finally:
                if job.queue_class == "generation":
                    self._generation_queue.task_done()
                elif job.queue_class == "favorite_backlog":
                    self._favorite_backlog_queue.task_done()
                else:
                    self._interactive_queue.task_done()

    async def _process_generation(self, gen_id: str) -> None:
        """Execute a single generation: build workflow, submit, poll, save."""
        cancel_event = self._get_cancel_event(gen_id)

        # Fetch record
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            )
            row = await cursor.fetchone()

        if row is None:
            self._cancel_events.pop(gen_id, None)
            return
        if row["status"] == "cancelled" or cancel_event.is_set():
            self._cancel_events.pop(gen_id, None)
            return

        # Claim the row for active processing and clear stale restart markers.
        async with get_db() as db:
            await db.execute(
                """UPDATE generations
                   SET status = ?,
                       error_message = NULL,
                       completed_at = NULL
                   WHERE id = ?""",
                ("running", gen_id),
            )
            await db.commit()

        start_time = time.perf_counter()

        try:
            # Build LoRA chain
            loras_data = _parse_json(row["loras"], [])
            lora_tuples = [
                (l["filename"], l["strength"])
                for l in loras_data
                if isinstance(l, dict)
            ]

            neg_prompt = row["negative_prompt"] or ""

            workflow, save_node_id = build_workflow(
                checkpoint=row["checkpoint"],
                loras=lora_tuples,
                positive_prompt=row["prompt"],
                negative_prompt=neg_prompt,
                seed=row["seed"],
                steps=row["steps"],
                cfg=row["cfg"],
                width=row["width"],
                height=row["height"],
                sampler=_normalize_sampler(row["sampler"]),
                scheduler=row["scheduler"],
                clip_skip=row.get("clip_skip"),
                filename_prefix=f"hollowforge_{gen_id[:8]}",
            )

            # Save workflow to disk
            save_workflow(workflow, gen_id)

            if cancel_event.is_set():
                await self._mark_generation_cancelled(gen_id)
                return

            # Submit to ComfyUI
            prompt_id = await self._client.submit_prompt(workflow)

            # Persist the prompt id and keep the row in a clean active state.
            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET status = ?,
                           error_message = NULL,
                           completed_at = NULL,
                           comfyui_prompt_id = ?
                       WHERE id = ?""",
                    ("running", prompt_id, gen_id),
                )
                await db.commit()

            if cancel_event.is_set():
                await self._client.cancel_prompt(prompt_id)
                await self._mark_generation_cancelled(gen_id)
                return

            # Poll for completion
            images = await self._client.wait_for_completion(
                prompt_id,
                save_node_id,
                cancel_check=cancel_event.is_set,
            )

            if cancel_event.is_set():
                await self._mark_generation_cancelled(gen_id)
                return

            # Download first image
            image_bytes = await self._client.download_image(images[0])

            # Save image + thumbnail
            image_path, thumb_path, wf_path = await save_generation_image(
                image_bytes, gen_id
            )
            watermark_settings = await self._load_watermark_settings()
            watermarked_path: str | None = None
            if watermark_settings.get("enabled"):
                try:
                    watermarked_path = await asyncio.to_thread(
                        apply_watermark,
                        image_path,
                        watermark_settings,
                    )
                except Exception:
                    logger.exception(
                        "Watermarking failed for generation %s; continuing without watermarked image",
                        gen_id,
                    )

            elapsed = time.perf_counter() - start_time

            # Mark completed
            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET status = ?, image_path = ?, thumbnail_path = ?,
                           workflow_path = ?, watermarked_path = ?,
                           error_message = NULL,
                           generation_time_sec = ?,
                           completed_at = ?
                       WHERE id = ?""",
                    (
                        "completed",
                        image_path,
                        thumb_path,
                        wf_path,
                        watermarked_path,
                        round(elapsed, 2),
                        _now_iso(),
                        gen_id,
                    ),
                )
                await db.commit()

        except ComfyUIWaitCancelledError:
            await self._mark_generation_cancelled(gen_id)
        except Exception as exc:
            if cancel_event.is_set():
                await self._mark_generation_cancelled(gen_id)
                return
            elapsed = time.perf_counter() - start_time
            logger.error(
                "Generation %s failed after %.2fs: %s", gen_id, elapsed, exc
            )
            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET status = ?, error_message = ?,
                           generation_time_sec = ?, completed_at = ?
                       WHERE id = ?""",
                    (
                        "failed",
                        str(exc)[:1000],
                        round(elapsed, 2),
                        _now_iso(),
                        gen_id,
                    ),
                )
                await db.commit()
        finally:
            self._cancel_events.pop(gen_id, None)

    async def _process_upscale(
        self,
        gen_id: str,
        upscale_model: str,
        mode: Literal["safe", "quality"] = "safe",
        denoise: float = 0.35,
        steps: int = 20,
    ) -> GenerationResponse:
        """Execute a single upscale job from an existing generated image."""
        row = await self._get_generation_row(gen_id)

        if row is None:
            raise ValueError(f"Generation {gen_id} not found")
        if row["status"] != "completed":
            raise ValueError("Only completed generations can be upscaled")
        source_image_path = row.get("image_path")
        if not source_image_path:
            raise ValueError("Generation has no source image to upscale")

        try:
            selected_upscale_model = upscale_model
            if not selected_upscale_model or selected_upscale_model.lower() == "auto":
                selected_upscale_model, profile = recommend_upscale_model(
                    row.get("checkpoint"),
                )
                if not selected_upscale_model:
                    raise ValueError("No local upscale model is available")
                logger.info(
                    "Auto-selected upscale model for %s: %s (profile=%s, checkpoint=%s)",
                    gen_id,
                    selected_upscale_model,
                    profile,
                    row.get("checkpoint"),
                )

            await self._set_postprocess_state(
                gen_id,
                "upscale",
                "running",
                f"Running {mode} upscale with {selected_upscale_model}",
            )
            full_image_path = pathlib.Path(settings.DATA_DIR / source_image_path).resolve()
            if not full_image_path.is_file():
                raise FileNotFoundError(
                    f"Source image not found: {full_image_path}"
                )

            local_model_path: pathlib.Path | None = None
            try:
                local_model_path = resolve_upscale_model_path(selected_upscale_model)
            except FileNotFoundError:
                local_model_path = None

            try:
                use_comfyui_safe = mode == "quality" or settings.UPSCALE_SAFE_USE_COMFYUI
                if use_comfyui_safe:
                    comfy_models = await self._client.get_upscale_models()
                    comfy_model_available = (
                        not comfy_models
                        or any(model.lower() == selected_upscale_model.lower() for model in comfy_models)
                    )
                    if comfy_models and not comfy_model_available and local_model_path is not None:
                        raise RuntimeError(
                            f"Upscale model '{selected_upscale_model}' is not registered in ComfyUI"
                        )
                    image_bytes = await self._run_comfyui_upscale(
                        gen_id=gen_id,
                        source_image_path=full_image_path,
                        upscale_model=selected_upscale_model,
                        mode=mode,
                        checkpoint=row.get("checkpoint") or settings.DEFAULT_CHECKPOINT,
                        positive_prompt=row.get("prompt") or "",
                        negative_prompt=row.get("negative_prompt") or "",
                        cfg=float(row["cfg"]) if row.get("cfg") is not None else 7.0,
                        seed=int(row["seed"]) if row.get("seed") is not None else 42,
                        denoise=denoise,
                        steps=steps,
                        clip_skip=row.get("clip_skip"),
                    )
                else:
                    logger.info(
                        "Safe upscale for %s bypassing ComfyUI; using CPU fallback only.",
                        gen_id,
                    )
                    image_bytes = await asyncio.to_thread(
                        run_safe_upscale,
                        full_image_path,
                        local_model_path
                        if local_model_path is not None
                        else resolve_upscale_model_path(selected_upscale_model),
                    )
            except Exception as comfy_exc:
                if mode == "quality":
                    raise RuntimeError(
                        f"Quality upscale failed ({comfy_exc})"
                    ) from comfy_exc
                logger.exception(
                    "Upscale failed for %s; falling back to CPU upscaler.",
                    gen_id,
                )
                try:
                    image_bytes = await asyncio.to_thread(
                        run_safe_upscale,
                        full_image_path,
                        local_model_path
                        if local_model_path is not None
                        else resolve_upscale_model_path(selected_upscale_model),
                    )
                except Exception as cpu_exc:
                    raise RuntimeError(
                        f"ComfyUI upscale failed ({comfy_exc}); CPU fallback failed ({cpu_exc})"
                    ) from cpu_exc

            upscaled_dir = settings.IMAGES_DIR / "upscaled"
            upscaled_dir.mkdir(parents=True, exist_ok=True)
            upscaled_file = upscaled_dir / f"{gen_id}.png"
            upscaled_file.write_bytes(image_bytes)
            upscaled_rel = f"images/upscaled/{gen_id}.png"
            upscaled_preview_rel = save_upscaled_preview(image_bytes, gen_id)

            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET upscaled_image_path = ?, upscaled_preview_path = ?,
                           upscale_model = ?, error_message = NULL,
                           postprocess_kind = NULL,
                           postprocess_status = NULL,
                           postprocess_message = NULL
                       WHERE id = ?""",
                    (upscaled_rel, upscaled_preview_rel, selected_upscale_model, gen_id),
                )
                await db.commit()
                cursor = await db.execute(
                    "SELECT * FROM generations WHERE id = ?", (gen_id,)
                )
                updated = await cursor.fetchone()

            if updated is None:
                raise RuntimeError(f"Generation {gen_id} disappeared after upscale")
            return _row_to_response(updated)
        except Exception as exc:
            logger.error("Upscale failed for %s: %s", gen_id, exc)
            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET error_message = ?,
                           postprocess_kind = 'upscale',
                           postprocess_status = 'failed',
                           postprocess_message = ?
                       WHERE id = ?""",
                    (str(exc)[:1000], str(exc)[:1000], gen_id),
                )
                await db.commit()
            raise

    async def _process_adetail(
        self,
        gen_id: str,
        denoise: float = 0.4,
        steps: int = 20,
    ) -> GenerationResponse:
        """Execute face inpainting detail fix on an existing generation."""
        try:
            await self._set_postprocess_state(
                gen_id,
                "adetail",
                "running",
                "Refining face details",
            )
            await adetailer_service.run_adetail(
                generation_id=gen_id,
                comfyui_client=self._client,
                denoise=denoise,
                steps=steps,
            )
            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET postprocess_kind = NULL,
                           postprocess_status = NULL,
                           postprocess_message = NULL,
                           error_message = NULL
                       WHERE id = ?""",
                    (gen_id,),
                )
                await db.commit()
                cursor = await db.execute(
                    "SELECT * FROM generations WHERE id = ?",
                    (gen_id,),
                )
                updated = await cursor.fetchone()

            if updated is None:
                raise RuntimeError(f"Generation {gen_id} disappeared after adetail")
            return _row_to_response(updated)
        except Exception as exc:
            logger.error("ADetail failed for %s: %s", gen_id, exc)
            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET error_message = ?,
                           postprocess_kind = 'adetail',
                           postprocess_status = 'failed',
                           postprocess_message = ?
                       WHERE id = ?""",
                    (str(exc)[:1000], str(exc)[:1000], gen_id),
                )
                await db.commit()
            raise

    async def _process_hiresfix(
        self,
        gen_id: str,
        upscale_factor: float = 1.5,
        denoise: float = 0.5,
        steps: int = 20,
        cfg: float = 7.0,
    ) -> GenerationResponse:
        """Execute latent upscale + second sampler pass on an existing generation."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?",
                (gen_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            raise ValueError(f"Generation {gen_id} not found")
        if row["status"] != "completed":
            raise ValueError("Only completed generations can run hiresfix")

        source_rel = row.get("upscaled_image_path") or row.get("image_path")
        if not source_rel:
            raise ValueError("Generation has no source image for hiresfix")

        try:
            await self._set_postprocess_state(
                gen_id,
                "hiresfix",
                "running",
                f"Running hiresfix at {upscale_factor:.2f}x",
            )
            source_path = pathlib.Path(settings.DATA_DIR / source_rel).resolve()
            if not source_path.is_file():
                raise FileNotFoundError(f"Source image not found: {source_path}")

            upload_filename = f"hollowforge_hiresfix_{gen_id}.png"
            comfy_filename = await self._client.upload_image(
                str(source_path), upload_filename
            )

            workflow, save_node_id = build_hiresfix_workflow(
                source_image_filename=comfy_filename,
                checkpoint=row.get("checkpoint") or settings.DEFAULT_CHECKPOINT,
                positive_prompt=row.get("prompt") or "",
                negative_prompt=row.get("negative_prompt") or "",
                seed=int(row.get("seed") or 0),
                upscale_factor=upscale_factor,
                denoise=denoise,
                steps=steps,
                cfg=cfg,
                sampler=row.get("sampler") or "euler",
                scheduler=row.get("scheduler") or "normal",
                filename_prefix=f"hollowforge_hiresfix_{gen_id[:8]}",
                clip_skip=row.get("clip_skip"),
            )

            prompt_id = await self._client.submit_prompt(workflow)
            images = await self._client.wait_for_completion(prompt_id, save_node_id)
            if not images:
                raise RuntimeError(
                    "ComfyUI hiresfix finished without output images"
                )

            image_bytes = await self._client.download_image(images[0])
            out_dir = settings.IMAGES_DIR / "hiresfix"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{gen_id}.png"
            out_path.write_bytes(image_bytes)
            out_rel = f"images/hiresfix/{gen_id}.png"

            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET hiresfix_path = ?, error_message = NULL,
                           postprocess_kind = NULL,
                           postprocess_status = NULL,
                           postprocess_message = NULL
                       WHERE id = ?""",
                    (out_rel, gen_id),
                )
                await db.commit()
                cursor = await db.execute(
                    "SELECT * FROM generations WHERE id = ?",
                    (gen_id,),
                )
                updated = await cursor.fetchone()

            if updated is None:
                raise RuntimeError(f"Generation {gen_id} disappeared after hiresfix")
            return _row_to_response(updated)
        except Exception as exc:
            logger.error("HiresFix failed for %s: %s", gen_id, exc)
            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET error_message = ?,
                           postprocess_kind = 'hiresfix',
                           postprocess_status = 'failed',
                           postprocess_message = ?
                       WHERE id = ?""",
                    (str(exc)[:1000], str(exc)[:1000], gen_id),
                )
                await db.commit()
            raise

    async def _run_comfyui_upscale(
        self,
        gen_id: str,
        source_image_path: pathlib.Path,
        upscale_model: str,
        mode: Literal["safe", "quality"],
        checkpoint: str,
        positive_prompt: str,
        negative_prompt: str,
        cfg: float,
        seed: int,
        denoise: float,
        steps: int,
        clip_skip: int | None,
    ) -> bytes:
        """Run upscale via ComfyUI with either the safe or staged-quality workflow."""
        upload_filename = f"hollowforge_upscale_{gen_id}.png"
        comfy_filename = await self._client.upload_image(
            str(source_image_path), upload_filename
        )

        if mode == "quality" and not settings.UPSCALE_QUALITY_ENABLED:
            raise RuntimeError("Quality upscale mode is disabled")
        if mode == "quality":
            missing_nodes = await self._client.missing_nodes(
                QUALITY_UPSCALE_REQUIRED_NODES
            )
            if missing_nodes:
                raise RuntimeError(
                    "Quality upscale workflow requires missing ComfyUI nodes: "
                    + ", ".join(missing_nodes)
                )
        else:
            logger.info(
                "Safe upscale mode selected. Using ImageUpscaleWithModel workflow."
            )

        if mode == "quality":
            with Image.open(source_image_path) as source:
                redraw_width, redraw_height = compute_quality_redraw_dimensions(
                    source.width,
                    source.height,
                    max_side=1024,
                )
            logger.info(
                "Quality upscale redraw target for %s: %sx%s",
                gen_id,
                redraw_width,
                redraw_height,
            )
            workflow, save_node_id = build_quality_upscale_workflow(
                image_filename=comfy_filename,
                upscale_model=upscale_model,
                checkpoint=checkpoint,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                denoise=min(denoise, 0.16),
                steps=min(steps, 10),
                cfg=min(cfg, 5.0),
                seed=seed,
                redraw_width=redraw_width,
                redraw_height=redraw_height,
                filename_prefix=f"hollowforge_upscaled_quality_{gen_id[:8]}",
                clip_skip=clip_skip,
            )
        else:
            workflow, save_node_id = build_upscale_workflow(
                image_filename=comfy_filename,
                upscale_model=upscale_model,
                filename_prefix=f"hollowforge_upscaled_{gen_id[:8]}",
            )

        prompt_id = await self._client.submit_prompt(workflow)
        images = await self._client.wait_for_completion(prompt_id, save_node_id)
        if not images:
            raise RuntimeError(
                "ComfyUI upscale finished without output images"
            )
        return await self._client.download_image(images[0])

    @staticmethod
    def _run_cpu_upscale(source_image_path: pathlib.Path, model_path: pathlib.Path) -> bytes:
        """Backward-compatible shim for the standalone safe runner."""
        return run_safe_upscale(source_image_path, model_path)
