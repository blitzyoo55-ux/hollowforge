"""Generation queue and background worker."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Literal

from PIL import Image

from app.config import settings
from app.db import get_db
from app.models import GenerationCreate, GenerationResponse, GenerationStatus, LoraInput
from app.services.comfyui_client import ComfyUIClient
from app.services.image_service import (
    save_generation_image,
    save_upscaled_preview,
    save_workflow,
)
from app.services.model_compatibility import is_checkpoint_compatible
from app.services.upscaler import TileUpscaler, resolve_upscale_model_path
from app.services.workflow_builder import build_workflow

logger = logging.getLogger(__name__)
_MAX_SEED = 2**31 - 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


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
        sampler=row["sampler"],
        scheduler=row["scheduler"],
        clip_skip=row.get("clip_skip"),
        status=row["status"],
        image_path=row.get("image_path"),
        upscaled_image_path=row.get("upscaled_image_path"),
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
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
    )


@dataclass
class _QueueJob:
    kind: Literal["generation", "upscale"]
    generation_id: str
    upscale_model: str | None = None
    result_future: asyncio.Future[GenerationResponse] | None = None


class GenerationService:
    """Manages the generation queue and background processing worker."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[_QueueJob] = asyncio.Queue()
        self._client = ComfyUIClient()
        self._worker_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_worker(self) -> None:
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def cleanup_stale(self) -> int:
        """Mark stale queued/running generations as failed on startup."""
        async with get_db() as db:
            cursor = await db.execute(
                """UPDATE generations
                   SET status = 'failed',
                       error_message = 'Server restarted',
                       completed_at = ?
                   WHERE status IN ('queued', 'running')""",
                (_now_iso(),),
            )
            await db.commit()
            return cursor.rowcount

    async def shutdown(self) -> None:
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        await self._client.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def queue_generation(self, gen: GenerationCreate) -> GenerationResponse:
        """Insert a new generation record and enqueue it for processing."""
        await self._validate_lora_compatibility(gen)
        seed = gen.resolved_seed()
        return await self._insert_generation_record(gen, seed)

    async def queue_generation_batch(
        self,
        gen: GenerationCreate,
        count: int,
        seed_increment: int = 1,
    ) -> tuple[int, list[GenerationResponse]]:
        """Queue N generations with auto-incremented seeds."""
        await self._validate_lora_compatibility(gen)
        if count < 2:
            raise ValueError("count must be >= 2 for batch generation")
        if seed_increment < 1:
            raise ValueError("seed_increment must be >= 1")

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

    async def _insert_generation_record(
        self, gen: GenerationCreate, seed: int
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

        await self._queue.put(_QueueJob(kind="generation", generation_id=gen_id))
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
        self, generation_id: str, upscale_model: str
    ) -> GenerationResponse:
        """Queue an upscale job on the same worker and wait for completion."""
        loop = asyncio.get_running_loop()
        result_future: asyncio.Future[GenerationResponse] = loop.create_future()
        await self._queue.put(
            _QueueJob(
                kind="upscale",
                generation_id=generation_id,
                upscale_model=upscale_model,
                result_future=result_future,
            )
        )
        return await result_future

    async def get_generation(self, gen_id: str) -> GenerationResponse | None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_response(row)

    async def get_generation_status(self, gen_id: str) -> GenerationStatus | None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, status, generation_time_sec, steps FROM generations WHERE id = ?",
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
        )

    async def cancel_generation(self, gen_id: str) -> bool:
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

            # Try to cancel in ComfyUI if running
            if row["status"] == "running" and row.get("comfyui_prompt_id"):
                await self._client.cancel_prompt(row["comfyui_prompt_id"])

            await db.execute(
                "UPDATE generations SET status = ?, completed_at = ? WHERE id = ?",
                ("cancelled", _now_iso(), gen_id),
            )
            await db.commit()
        return True

    # ------------------------------------------------------------------
    # Background worker
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        """Process queue jobs one at a time."""
        while True:
            job = await self._queue.get()
            try:
                if job.kind == "generation":
                    await self._process_generation(job.generation_id)
                elif job.kind == "upscale":
                    result = await self._process_upscale(
                        job.generation_id, job.upscale_model or "remacri_original.safetensors"
                    )
                    if job.result_future and not job.result_future.done():
                        job.result_future.set_result(result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if job.kind == "upscale" and job.result_future and not job.result_future.done():
                    job.result_future.set_exception(exc)
                else:
                    logger.exception(
                        "Unhandled error processing %s job for generation %s",
                        job.kind,
                        job.generation_id,
                    )
            finally:
                self._queue.task_done()

    async def _process_generation(self, gen_id: str) -> None:
        """Execute a single generation: build workflow, submit, poll, save."""
        # Fetch record
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            )
            row = await cursor.fetchone()

        if row is None or row["status"] == "cancelled":
            return

        # Update status to running
        async with get_db() as db:
            await db.execute(
                "UPDATE generations SET status = ? WHERE id = ?",
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
                sampler=row["sampler"],
                scheduler=row["scheduler"],
                clip_skip=row.get("clip_skip"),
                filename_prefix=f"hollowforge_{gen_id[:8]}",
            )

            # Save workflow to disk
            save_workflow(workflow, gen_id)

            # Submit to ComfyUI
            prompt_id = await self._client.submit_prompt(workflow)

            # Store prompt_id
            async with get_db() as db:
                await db.execute(
                    "UPDATE generations SET comfyui_prompt_id = ? WHERE id = ?",
                    (prompt_id, gen_id),
                )
                await db.commit()

            # Poll for completion
            images = await self._client.wait_for_completion(
                prompt_id, save_node_id
            )

            # Download first image
            image_bytes = await self._client.download_image(images[0])

            # Save image + thumbnail
            image_path, thumb_path, wf_path = await save_generation_image(
                image_bytes, gen_id
            )

            elapsed = time.perf_counter() - start_time

            # Mark completed
            async with get_db() as db:
                await db.execute(
                    """UPDATE generations
                       SET status = ?, image_path = ?, thumbnail_path = ?,
                           workflow_path = ?, generation_time_sec = ?,
                           completed_at = ?
                       WHERE id = ?""",
                    (
                        "completed",
                        image_path,
                        thumb_path,
                        wf_path,
                        round(elapsed, 2),
                        _now_iso(),
                        gen_id,
                    ),
                )
                await db.commit()

        except Exception as exc:
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

    async def _process_upscale(
        self, gen_id: str, upscale_model: str
    ) -> GenerationResponse:
        """Execute a single upscale job from an existing generated image."""
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            )
            row = await cursor.fetchone()

        if row is None:
            raise ValueError(f"Generation {gen_id} not found")
        if row["status"] != "completed":
            raise ValueError("Only completed generations can be upscaled")
        source_image_path = row.get("image_path")
        if not source_image_path:
            raise ValueError("Generation has no source image to upscale")

        try:
            full_image_path = (settings.DATA_DIR / source_image_path).resolve()
            model_path = resolve_upscale_model_path(upscale_model)

            def _run_upscale() -> bytes:
                upscaler = TileUpscaler(model_path)
                with Image.open(full_image_path) as source:
                    upscaled = upscaler.upscale(source, tile_size=512, overlap=32)
                out = BytesIO()
                upscaled.save(out, format="PNG", optimize=True)
                return out.getvalue()

            image_bytes = await asyncio.to_thread(_run_upscale)

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
                           upscale_model = ?, error_message = NULL
                       WHERE id = ?""",
                    (upscaled_rel, upscaled_preview_rel, upscale_model, gen_id),
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
                    "UPDATE generations SET error_message = ? WHERE id = ?",
                    (str(exc)[:1000], gen_id),
                )
                await db.commit()
            raise
