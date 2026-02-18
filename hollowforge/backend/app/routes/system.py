"""System health and status endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Request

from app.db import get_db
from app.models import ComfyUIConfigUpdate, SystemHealth
from app.services.comfyui_client import ComfyUIClient

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.post("/sync")
async def sync_models(request: Request) -> dict:
    """Refresh models/LoRAs from ComfyUI and return current lists."""
    client: ComfyUIClient = request.app.state.comfyui_client
    checkpoints = await client.get_models()
    samplers = await client.get_samplers()
    schedulers = await client.get_schedulers()
    lora_files = await client.get_lora_files()

    new_loras = 0
    async with get_db() as db:
        cursor = await db.execute("SELECT filename FROM lora_profiles")
        rows = await cursor.fetchall()
        existing_filenames = {row["filename"] for row in rows}

        missing_filenames = [
            filename for filename in lora_files if filename not in existing_filenames
        ]
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        for filename in missing_filenames:
            display_name = filename
            if display_name.endswith(".safetensors"):
                display_name = display_name[: -len(".safetensors")]
            display_name = display_name.replace("_", " ")

            await db.execute(
                """
                INSERT INTO lora_profiles
                    (id, display_name, filename, category, default_strength, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), display_name, filename, "style", 0.5, now),
            )
            new_loras += 1

        if new_loras > 0:
            await db.commit()

    return {
        "checkpoints": checkpoints,
        "samplers": samplers,
        "schedulers": schedulers,
        "lora_files": lora_files,
        "new_loras": new_loras,
        "synced": True,
    }


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


@router.post("/comfyui")
async def update_comfyui_url(payload: ComfyUIConfigUpdate, request: Request) -> dict:
    """Update ComfyUI base URL at runtime and verify connectivity."""
    client: ComfyUIClient = request.app.state.comfyui_client
    await client.set_base_url(payload.url)
    connected = await client.check_health()
    return {
        "connected": connected,
        "url": client.base_url,
        "message": "Connected successfully" if connected else "ComfyUI is not responding",
    }


@router.get("/models")
async def list_models(request: Request) -> dict:
    """List available checkpoint models, samplers, and schedulers from ComfyUI."""
    client: ComfyUIClient = request.app.state.comfyui_client
    checkpoints = await client.get_models()
    samplers = await client.get_samplers()
    schedulers = await client.get_schedulers()
    lora_files = await client.get_lora_files()
    return {
        "checkpoints": checkpoints,
        "samplers": samplers,
        "schedulers": schedulers,
        "lora_files": lora_files,
    }


@router.get("/upscale-models")
async def list_upscale_models(request: Request) -> dict:
    """List available upscaler models from ComfyUI."""
    client: ComfyUIClient = request.app.state.comfyui_client
    upscale_models = await client.get_upscale_models()
    return {"upscale_models": upscale_models}
