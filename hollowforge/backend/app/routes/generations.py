"""Generation CRUD and queue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.models import GenerationCreate, GenerationResponse, GenerationStatus
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
    return await service.queue_generation(gen)


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
