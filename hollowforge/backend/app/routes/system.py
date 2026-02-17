"""System health and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.db import get_db
from app.models import SystemHealth
from app.services.comfyui_client import ComfyUIClient

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/health", response_model=SystemHealth)
async def health_check(request: Request) -> SystemHealth:
    """Overall system health."""
    client: ComfyUIClient = request.app.state.comfyui_client
    comfyui_ok = await client.check_health()

    db_ok = False
    total_generations = 0
    try:
        async with get_db() as db:
            cursor = await db.execute("SELECT COUNT(*) AS cnt FROM generations")
            row = await cursor.fetchone()
            total_generations = row["cnt"] if row else 0
            db_ok = True
    except Exception:
        pass

    status = "healthy" if (comfyui_ok and db_ok) else "degraded"
    return SystemHealth(
        status=status,
        comfyui_connected=comfyui_ok,
        db_ok=db_ok,
        total_generations=total_generations,
    )


@router.get("/comfyui")
async def comfyui_status(request: Request) -> dict:
    """Check ComfyUI connectivity."""
    client: ComfyUIClient = request.app.state.comfyui_client
    connected = await client.check_health()
    return {"connected": connected, "url": client.base_url}


@router.get("/models")
async def list_models(request: Request) -> dict:
    """List available checkpoint models from ComfyUI."""
    client: ComfyUIClient = request.app.state.comfyui_client
    models = await client.get_models()
    return {"models": models}
