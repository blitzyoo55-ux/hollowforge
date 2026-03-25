"""Generation CRUD and queue endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.db import get_db
from app.models import (
    ADetailRequest,
    GenerationBatchCreate,
    GenerationBatchResponse,
    GenerationCreate,
    GenerationResponse,
    GenerationStatus,
    HiresFixRequest,
    LoraInput,
    UpscaleRequest,
)
from app.services.generation_service import GenerationService

router = APIRouter(prefix="/api/v1/generations", tags=["generations"])


def _get_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


def _parse_json_field(raw: str | None, default: Any = None) -> Any:
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def _resume_note(base_note: str | None, restart_completed_at: str) -> str:
    prefix = (base_note or "").strip() or "Recovered generation"
    return f"{prefix} [recovered restart {restart_completed_at}]"


def _generation_create_from_row(
    row: dict[str, Any],
    *,
    notes: str,
    source_id: str,
) -> GenerationCreate:
    loras_raw = _parse_json_field(row.get("loras"), [])
    loras = [
        LoraInput(**entry) if isinstance(entry, dict) else entry
        for entry in loras_raw
    ]
    tags = _parse_json_field(row.get("tags"))
    return GenerationCreate(
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
        tags=tags,
        preset_id=row.get("preset_id"),
        notes=notes,
        source_id=source_id,
    )


@router.post(
    "",
    response_model=GenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_generation(
    gen: GenerationCreate, request: Request
) -> GenerationResponse:
    """Queue a new image generation."""
    service = _get_service(request)
    try:
        return await service.queue_generation(gen)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/batch",
    response_model=GenerationBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_generation_batch(
    payload: GenerationBatchCreate, request: Request
) -> GenerationBatchResponse:
    """Queue multiple generations with auto-incremented seeds."""
    service = _get_service(request)
    try:
        base_seed, queued = await service.queue_generation_batch(
            payload.generation,
            payload.count,
            payload.seed_increment,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return GenerationBatchResponse(
        count=payload.count,
        base_seed=base_seed,
        seed_increment=payload.seed_increment,
        generations=queued,
    )


@router.get("/active")
async def get_active_generations() -> list[dict[str, str | int]]:
    """Fetch currently queued or running generations."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, status, created_at, checkpoint, seed, steps, width, height
               FROM generations
               WHERE status IN ('queued', 'running')
               ORDER BY created_at ASC"""
        )
        rows = await cursor.fetchall()

    return [
        {
            "id": row["id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "checkpoint": row["checkpoint"],
            "seed": row["seed"],
            "steps": row["steps"],
            "width": row["width"],
            "height": row["height"],
        }
        for row in rows
    ]


@router.get("/queue/summary")
async def get_queue_summary() -> dict:
    """Return queue summary with estimated times for each item."""
    import json as _json

    async with get_db() as db:
        # Average generation time from last 20 completed
        avg_cursor = await db.execute(
            """SELECT generation_time_sec FROM generations
               WHERE status = 'completed' AND generation_time_sec IS NOT NULL
               ORDER BY completed_at DESC LIMIT 20"""
        )
        avg_rows = await avg_cursor.fetchall()
        if avg_rows:
            avg_gen_sec = sum(r["generation_time_sec"] for r in avg_rows) / len(avg_rows)
        else:
            avg_gen_sec = 90.0

        # All queued/running items ordered by created_at
        q_cursor = await db.execute(
            """SELECT id, status, checkpoint, loras, prompt, steps, cfg,
                      width, height, sampler, tags, notes, created_at,
                      generation_time_sec
               FROM generations
               WHERE status IN ('queued', 'running')
               ORDER BY created_at ASC"""
        )
        rows = await q_cursor.fetchall()

    total_queued = 0
    total_running = 0
    oldest_queued_at = None
    queue_items = []

    # First pass: find running item's elapsed time for estimate
    running_elapsed_sec = 0.0
    for row in rows:
        if row["status"] == "running":
            from datetime import datetime, timezone

            try:
                created = datetime.fromisoformat(row["created_at"])
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                running_elapsed_sec = max(0, (now - created).total_seconds())
            except Exception:
                running_elapsed_sec = 0.0
            break

    running_remaining = max(0, avg_gen_sec - running_elapsed_sec)
    cumulative_sec = running_remaining if any(r["status"] == "running" for r in rows) else 0.0

    position = 0
    for row in rows:
        position += 1
        st = row["status"]
        if st == "queued":
            total_queued += 1
            if oldest_queued_at is None:
                oldest_queued_at = row["created_at"]
        elif st == "running":
            total_running += 1

        # Parse JSON fields
        try:
            loras = _json.loads(row["loras"]) if row["loras"] else []
        except Exception:
            loras = []
        try:
            tags = _json.loads(row["tags"]) if row["tags"] else None
        except Exception:
            tags = None

        prompt_text = (row["prompt"] or "")[:80]

        if st == "running":
            est_start = 0.0
            est_done = running_remaining
        else:
            est_start = cumulative_sec
            est_done = cumulative_sec + avg_gen_sec
            cumulative_sec += avg_gen_sec

        queue_items.append(
            {
                "id": row["id"],
                "status": st,
                "position": position,
                "checkpoint": row["checkpoint"],
                "loras": loras,
                "prompt": prompt_text,
                "steps": row["steps"],
                "cfg": row["cfg"],
                "width": row["width"],
                "height": row["height"],
                "sampler": row["sampler"],
                "tags": tags,
                "notes": row["notes"],
                "created_at": row["created_at"],
                "estimated_start_sec": round(est_start, 1),
                "estimated_done_sec": round(est_done, 1),
            }
        )

    total_active = total_queued + total_running
    estimated_remaining = round(cumulative_sec, 1) if total_active > 0 else 0.0

    return {
        "total_queued": total_queued,
        "total_running": total_running,
        "total_active": total_active,
        "avg_generation_sec": round(avg_gen_sec, 1),
        "estimated_remaining_sec": estimated_remaining,
        "oldest_queued_at": oldest_queued_at,
        "queue_items": queue_items,
    }


@router.post("/recover/server-restarted/latest")
async def recover_latest_server_restarted_generations(request: Request) -> dict:
    """Requeue the most recent cluster of generations failed by startup stale cleanup."""
    service = _get_service(request)

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT DISTINCT completed_at
            FROM generations
            WHERE status = 'failed' AND error_message = 'Server restarted'
            ORDER BY completed_at DESC
            """
        )
        restart_points = [row["completed_at"] for row in await cursor.fetchall()]

        if not restart_points:
            return {
                "restart_completed_at": None,
                "found": 0,
                "queued": 0,
                "skipped": 0,
                "errors": [],
            }

        restart_completed_at = None
        rows = []
        for candidate_completed_at in restart_points:
            cursor = await db.execute(
                """
                SELECT *
                FROM generations
                WHERE status = 'failed'
                  AND error_message = 'Server restarted'
                  AND completed_at = ?
                ORDER BY created_at ASC
                """,
                (candidate_completed_at,),
            )
            candidate_rows = await cursor.fetchall()
            recoverable = False
            for row in candidate_rows:
                resume_note = _resume_note(row.get("notes"), candidate_completed_at)
                existing_cursor = await db.execute(
                    """
                    SELECT 1
                    FROM generations
                    WHERE source_id = ? AND notes = ?
                    LIMIT 1
                    """,
                    (row["id"], resume_note),
                )
                existing = await existing_cursor.fetchone()
                if existing is None:
                    recoverable = True
                    break
            if recoverable:
                restart_completed_at = candidate_completed_at
                rows = candidate_rows
                break

        if restart_completed_at is None:
            return {
                "restart_completed_at": None,
                "found": 0,
                "queued": 0,
                "skipped": 0,
                "errors": [],
            }

    queued: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for row in rows:
        resume_note = _resume_note(row.get("notes"), restart_completed_at)
        async with get_db() as db:
            cursor = await db.execute(
                """
                SELECT id
                FROM generations
                WHERE source_id = ? AND notes = ?
                LIMIT 1
                """,
                (row["id"], resume_note),
            )
            existing = await cursor.fetchone()

        if existing is not None:
            skipped.append(
                {
                    "source_id": row["id"],
                    "existing_generation_id": existing["id"],
                }
            )
            continue

        try:
            generation = _generation_create_from_row(
                row,
                notes=resume_note,
                source_id=row["id"],
            )
            queued_row = await service.queue_generation(generation)
        except ValueError as exc:
            errors.append(
                {
                    "source_id": row["id"],
                    "notes": row.get("notes") or "",
                    "error": str(exc),
                }
            )
            continue

        queued.append(
            {
                "source_id": row["id"],
                "generation_id": queued_row.id,
            }
        )

    return {
        "restart_completed_at": restart_completed_at,
        "found": len(rows),
        "queued": len(queued),
        "skipped": len(skipped),
        "errors": errors,
        "queued_generation_ids_sample": queued[:10],
        "skipped_generation_ids_sample": skipped[:10],
    }


@router.post("/cancel-all-queued")
async def cancel_all_queued() -> dict:
    """Cancel all queued generations."""
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE generations SET status = 'cancelled' WHERE status = 'queued'"
        )
        count = cursor.rowcount
        await db.commit()
    return {"cancelled": count}


@router.get("/{generation_id}", response_model=GenerationResponse)
async def get_generation(
    generation_id: str, request: Request
) -> GenerationResponse:
    """Fetch a single generation by ID."""
    service = _get_service(request)
    result = await service.get_generation(generation_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )
    return result


@router.get("/{generation_id}/status", response_model=GenerationStatus)
async def get_generation_status(
    generation_id: str, request: Request
) -> GenerationStatus:
    """Lightweight status poll for a generation."""
    service = _get_service(request)
    result = await service.get_generation_status(generation_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )
    return result


@router.post("/{generation_id}/cancel")
async def cancel_generation(generation_id: str, request: Request) -> dict:
    """Cancel a queued or running generation."""
    service = _get_service(request)
    success = await service.cancel_generation(generation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found or already terminal",
        )
    return {"success": True}


@router.post(
    "/{generation_id}/upscale",
    response_model=GenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upscale_generation(
    generation_id: str,
    payload: UpscaleRequest,
    request: Request,
) -> GenerationResponse:
    """Queue an upscale job and return immediately."""
    service = _get_service(request)
    existing = await service.get_generation(generation_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )
    if existing.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed generations can be upscaled",
        )
    if not existing.image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generation has no image_path",
        )

    try:
        return await service.queue_upscale(
            generation_id,
            payload.upscale_model,
            mode=payload.mode,
            denoise=payload.denoise,
            steps=payload.steps,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post(
    "/{generation_id}/adetail",
    response_model=GenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def adetail_generation(
    generation_id: str,
    payload: ADetailRequest,
    request: Request,
) -> GenerationResponse:
    """Queue an ADetail-like face inpaint fix and return immediately."""
    service = _get_service(request)
    existing = await service.get_generation(generation_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )
    if existing.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed generations can run adetail",
        )
    if not existing.image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generation has no image_path",
        )

    try:
        return await service.queue_adetail(
            generation_id,
            denoise=payload.denoise,
            steps=payload.steps,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/{generation_id}/hiresfix",
    response_model=GenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def hiresfix_generation(
    generation_id: str,
    payload: HiresFixRequest,
    request: Request,
) -> GenerationResponse:
    """Queue a latent upscale + second pass sampler job and return immediately."""
    service = _get_service(request)
    existing = await service.get_generation(generation_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )
    if existing.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed generations can run hiresfix",
        )
    if not existing.image_path and not existing.upscaled_image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generation has no source image",
        )

    try:
        return await service.queue_hiresfix(
            generation_id,
            upscale_factor=payload.upscale_factor,
            denoise=payload.denoise,
            steps=payload.steps,
            cfg=payload.cfg,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{generation_id}/watermark", response_model=GenerationResponse)
async def watermark_generation(
    generation_id: str,
    request: Request,
) -> GenerationResponse:
    """Apply watermark to an existing completed generation."""
    service = _get_service(request)
    try:
        return await service.apply_watermark_to_generation(generation_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
