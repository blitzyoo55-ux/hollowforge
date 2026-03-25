"""Benchmark run/list/detail endpoints."""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.db import get_db
from app.models import BenchmarkCreate, BenchmarkResponse, GenerationCreate, LoraInput
from app.services.generation_service import GenerationService

router = APIRouter(prefix="/api/v1/benchmark", tags=["benchmark"])

_TERMINAL_GENERATION_STATES = {"completed", "failed", "cancelled"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _get_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


def _row_to_response(
    row: dict[str, Any],
    generations: list[Any] | None = None,
) -> BenchmarkResponse:
    loras_raw = _parse_json(row.get("loras"), [])
    loras = [LoraInput(**item) for item in loras_raw if isinstance(item, dict)]
    checkpoints = _parse_json(row.get("checkpoints"), [])
    generation_ids = _parse_json(row.get("generation_ids"), [])
    return BenchmarkResponse(
        id=row["id"],
        name=row["name"],
        prompt=row["prompt"],
        negative_prompt=row.get("negative_prompt"),
        loras=loras,
        steps=row["steps"],
        cfg=row["cfg"],
        width=row["width"],
        height=row["height"],
        sampler=row["sampler"],
        scheduler=row["scheduler"],
        seed=row.get("seed"),
        checkpoints=checkpoints,
        generation_ids=generation_ids,
        status=row["status"],
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
        generations=generations,
    )


def _aggregate_benchmark_status(generation_statuses: list[str]) -> str:
    if not generation_statuses:
        return "pending"
    if any(status in {"queued", "running"} for status in generation_statuses):
        return "running"
    if all(status == "completed" for status in generation_statuses):
        return "completed"
    if all(status in _TERMINAL_GENERATION_STATES for status in generation_statuses):
        return "failed"
    return "running"


async def _refresh_benchmark_status(
    db,
    row: dict[str, Any],
) -> dict[str, Any]:
    generation_ids = _parse_json(row.get("generation_ids"), [])
    status = row.get("status", "pending")
    completed_at = row.get("completed_at")

    if generation_ids:
        placeholders = ",".join("?" for _ in generation_ids)
        cursor = await db.execute(
            f"SELECT id, status FROM generations WHERE id IN ({placeholders})",
            generation_ids,
        )
        status_rows = await cursor.fetchall()
        by_id = {entry["id"]: entry["status"] for entry in status_rows}
        statuses = [by_id.get(gen_id, "failed") for gen_id in generation_ids]
        status = _aggregate_benchmark_status(statuses)
    else:
        status = status if status in {"failed", "completed"} else "pending"

    if status in {"completed", "failed"}:
        next_completed_at = completed_at or _now_iso()
    else:
        next_completed_at = None

    if status != row.get("status") or next_completed_at != completed_at:
        await db.execute(
            "UPDATE benchmark_jobs SET status = ?, completed_at = ? WHERE id = ?",
            (status, next_completed_at, row["id"]),
        )
        await db.commit()

    refreshed = dict(row)
    refreshed["status"] = status
    refreshed["completed_at"] = next_completed_at
    return refreshed


@router.post(
    "/run",
    response_model=BenchmarkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_benchmark(
    payload: BenchmarkCreate,
    request: Request,
) -> BenchmarkResponse:
    service = _get_service(request)

    checkpoints = [cp.strip() for cp in payload.checkpoints if cp.strip()]
    if len(checkpoints) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 checkpoints are required",
        )
    if len(checkpoints) != len(set(checkpoints)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate checkpoints are not allowed",
        )

    fixed_seed = (
        payload.seed
        if payload.seed is not None and payload.seed != -1
        else random.randint(0, 2**31 - 1)
    )

    job_id = str(uuid.uuid4())
    now = _now_iso()

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO benchmark_jobs (
                id, name, prompt, negative_prompt, loras,
                steps, cfg, width, height, sampler, scheduler,
                seed, checkpoints, generation_ids, status, created_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                job_id,
                payload.name,
                payload.prompt,
                payload.negative_prompt,
                json.dumps([lora.model_dump() for lora in payload.loras]),
                payload.steps,
                payload.cfg,
                payload.width,
                payload.height,
                payload.sampler,
                payload.scheduler,
                fixed_seed,
                json.dumps(checkpoints),
                json.dumps([]),
                "pending",
                now,
            ),
        )
        await db.commit()

    generation_ids: list[str] = []
    try:
        for checkpoint in checkpoints:
            queued = await service.queue_generation(
                GenerationCreate(
                    prompt=payload.prompt,
                    negative_prompt=payload.negative_prompt,
                    checkpoint=checkpoint,
                    loras=payload.loras,
                    seed=fixed_seed,
                    steps=payload.steps,
                    cfg=payload.cfg,
                    width=payload.width,
                    height=payload.height,
                    sampler=payload.sampler,
                    scheduler=payload.scheduler,
                )
            )
            generation_ids.append(queued.id)
    except ValueError as exc:
        async with get_db() as db:
            await db.execute(
                """
                UPDATE benchmark_jobs
                SET generation_ids = ?, status = 'failed', completed_at = ?
                WHERE id = ?
                """,
                (json.dumps(generation_ids), _now_iso(), job_id),
            )
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        async with get_db() as db:
            await db.execute(
                """
                UPDATE benchmark_jobs
                SET generation_ids = ?, status = 'failed', completed_at = ?
                WHERE id = ?
                """,
                (json.dumps(generation_ids), _now_iso(), job_id),
            )
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue benchmark: {exc}",
        ) from exc

    async with get_db() as db:
        await db.execute(
            """
            UPDATE benchmark_jobs
            SET generation_ids = ?, status = 'running'
            WHERE id = ?
            """,
            (json.dumps(generation_ids), job_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM benchmark_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist benchmark job",
        )

    return _row_to_response(row)


@router.get("/jobs", response_model=list[BenchmarkResponse])
async def list_benchmark_jobs() -> list[BenchmarkResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM benchmark_jobs ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()

        refreshed_rows: list[dict[str, Any]] = []
        for row in rows:
            refreshed_rows.append(await _refresh_benchmark_status(db, row))

    return [_row_to_response(row) for row in refreshed_rows]


@router.get("/jobs/{job_id}", response_model=BenchmarkResponse)
async def get_benchmark_job(
    job_id: str,
    request: Request,
) -> BenchmarkResponse:
    service = _get_service(request)

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM benchmark_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Benchmark job {job_id} not found",
            )

        refreshed = await _refresh_benchmark_status(db, row)

    generation_ids = _parse_json(refreshed.get("generation_ids"), [])
    generations: list[Any] = []
    for generation_id in generation_ids:
        generation = await service.get_generation(generation_id)
        if generation is None:
            generations.append({"id": generation_id, "status": "missing"})
        else:
            generations.append(generation.model_dump())

    return _row_to_response(refreshed, generations=generations)


@router.delete("/jobs/{job_id}")
async def delete_benchmark_job(job_id: str) -> dict[str, bool]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM benchmark_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Benchmark job {job_id} not found",
            )

        await db.execute("DELETE FROM benchmark_jobs WHERE id = ?", (job_id,))
        await db.commit()

    return {"success": True}
