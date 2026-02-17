"""Generation queue and background worker."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from app.config import settings
from app.db import get_db
from app.models import GenerationCreate, GenerationResponse, GenerationStatus, LoraInput
from app.services.comfyui_client import ComfyUIClient
from app.services.image_service import save_generation_image, save_workflow
from app.services.workflow_builder import build_workflow

logger = logging.getLogger(__name__)


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
        status=row["status"],
        image_path=row.get("image_path"),
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


class GenerationService:
    """Manages the generation queue and background processing worker."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._client = ComfyUIClient()
        self._worker_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_worker(self) -> None:
        self._worker_task = asyncio.create_task(self._worker_loop())

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
        gen_id = str(uuid.uuid4())
        seed = gen.resolved_seed()
        now = _now_iso()

        loras_json = json.dumps([l.model_dump() for l in gen.loras])
        tags_json = json.dumps(gen.tags) if gen.tags else None

        async with get_db() as db:
            await db.execute(
                """INSERT INTO generations
                   (id, prompt, negative_prompt, checkpoint, loras, seed,
                    steps, cfg, width, height, sampler, scheduler,
                    status, tags, preset_id, notes, source_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    gen_id, gen.prompt, gen.negative_prompt, gen.checkpoint,
                    loras_json, seed, gen.steps, gen.cfg, gen.width, gen.height,
                    gen.sampler, gen.scheduler, "queued", tags_json,
                    gen.preset_id, gen.notes, gen.source_id, now,
                ),
            )
            await db.commit()

            cursor = await db.execute(
                "SELECT * FROM generations WHERE id = ?", (gen_id,)
            )
            row = await cursor.fetchone()

        await self._queue.put(gen_id)
        return _row_to_response(row)

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
                "SELECT id, status, generation_time_sec FROM generations WHERE id = ?",
                (gen_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return GenerationStatus(
            id=row["id"],
            status=row["status"],
            generation_time_sec=row.get("generation_time_sec"),
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
        """Process generation jobs from the queue one at a time."""
        while True:
            gen_id = await self._queue.get()
            try:
                await self._process_generation(gen_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unhandled error processing generation %s", gen_id)
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
                        "completed", image_path, thumb_path, wf_path,
                        round(elapsed, 2), _now_iso(), gen_id,
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
                        "failed", str(exc)[:1000], round(elapsed, 2),
                        _now_iso(), gen_id,
                    ),
                )
                await db.commit()
