"""Generation CRUD and queue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.db import get_db
from app.models import (
    GenerationBatchCreate,
    GenerationBatchResponse,
    GenerationCreate,
    GenerationResponse,
    GenerationStatus,
    UpscaleRequest,
)
from app.services.generation_service import GenerationService

router = APIRouter(prefix="/api/v1/generations", tags=["generations"])


def _get_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


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
async def get_active_generations() -> list[dict[str, str]]:
    """Fetch currently queued or running generations."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, status, created_at
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
        }
        for row in rows
    ]


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


@router.post("/{generation_id}/upscale", response_model=GenerationResponse)
async def upscale_generation(
    generation_id: str,
    payload: UpscaleRequest,
    request: Request,
) -> GenerationResponse:
    """Upscale an existing completed generation via the shared queue worker."""
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
        return await service.queue_upscale(generation_id, payload.upscale_model)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
