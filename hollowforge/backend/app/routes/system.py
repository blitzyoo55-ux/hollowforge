"""System health and status endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request

from app.db import get_db
from app.models import ComfyUIConfigUpdate, SystemHealth
from app.services.comfyui_client import ComfyUIClient
from app.services.model_compatibility import (
    build_lora_compatibility_snapshot,
    dump_compatible_checkpoints,
)

router = APIRouter(prefix="/api/v1/system", tags=["system"])

_NON_IMAGE_ARCHES = {"WAN-I2V-14B", "SVD-XT"}


def _pick_first_available(
    preferred: list[str], available: list[str], fallback: str
) -> str:
    available_set = set(available)
    for item in preferred:
        if item in available_set:
            return item
    if available:
        return available[0]
    return fallback


def _quality_profile_for_arch(
    architecture: str, samplers: list[str], schedulers: list[str]
) -> dict[str, Any]:
    if architecture in _NON_IMAGE_ARCHES:
        return {
            "applicable": False,
            "profile_name": "Non-image checkpoint",
            "description": "This checkpoint is video/specialized and excluded from image workflow.",
            "params": None,
        }

    if architecture == "SD1.5":
        return {
            "applicable": True,
            "profile_name": "SD1.5 Balanced Portrait",
            "description": "Conservative defaults for SD1.5 quality and stability.",
            "params": {
                "steps": 30,
                "cfg": 7.0,
                "width": 768,
                "height": 1152,
                "sampler": _pick_first_available(
                    ["dpmpp_2m", "euler_ancestral", "euler"],
                    samplers,
                    "euler",
                ),
                "scheduler": _pick_first_available(
                    ["karras", "normal"],
                    schedulers,
                    "normal",
                ),
                "clip_skip": None,
            },
        }

    if architecture == "FLUX":
        return {
            "applicable": True,
            "profile_name": "FLUX Base (Experimental)",
            "description": "FLUX defaults; validate workflow compatibility before production use.",
            "params": {
                "steps": 24,
                "cfg": 3.5,
                "width": 1024,
                "height": 1024,
                "sampler": _pick_first_available(["euler", "dpmpp_2m"], samplers, "euler"),
                "scheduler": _pick_first_available(["normal", "karras"], schedulers, "normal"),
                "clip_skip": None,
            },
        }

    # Default: SDXL-family and unknown image models
    return {
        "applicable": True,
        "profile_name": "SDXL Quality Balanced",
        "description": "Benchmark-aligned defaults for SDXL-based checkpoints.",
        "params": {
            "steps": 28,
            "cfg": 7.0,
            "width": 832,
            "height": 1216,
            "sampler": _pick_first_available(["euler", "dpmpp_2m", "euler_ancestral"], samplers, "euler"),
            "scheduler": _pick_first_available(["normal", "karras"], schedulers, "normal"),
            "clip_skip": None,
        },
    }


def _split_checkpoints_by_image_capability(
    checkpoints: list[str], checkpoint_arches: dict[str, str]
) -> tuple[list[str], list[str]]:
    image: list[str] = []
    non_image: list[str] = []
    for checkpoint in checkpoints:
        arch = checkpoint_arches.get(checkpoint, "Unknown")
        if arch in _NON_IMAGE_ARCHES:
            non_image.append(checkpoint)
        else:
            image.append(checkpoint)
    return image, non_image


@router.post("/sync")
async def sync_models(request: Request) -> dict:
    """Refresh models/LoRAs from ComfyUI and return current lists."""
    client: ComfyUIClient = request.app.state.comfyui_client
    checkpoints = await client.get_models()
    samplers = await client.get_samplers()
    schedulers = await client.get_schedulers()
    lora_files = await client.get_lora_files()
    checkpoint_arches, lora_analysis = build_lora_compatibility_snapshot(
        checkpoints, lora_files
    )
    image_checkpoints, non_image_checkpoints = _split_checkpoints_by_image_capability(
        checkpoints, checkpoint_arches
    )

    new_loras = 0
    compatibility_updated = 0
    incompatible_loras = 0
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
            analysis = lora_analysis.get(filename)
            category = analysis.category if analysis else "style"
            default_strength = (
                analysis.default_strength if analysis else 0.5
            )

            await db.execute(
                """
                INSERT INTO lora_profiles
                    (id, display_name, filename, category, default_strength, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    display_name,
                    filename,
                    category,
                    default_strength,
                    now,
                ),
            )
            new_loras += 1
            existing_filenames.add(filename)

        for filename in lora_files:
            if filename not in existing_filenames:
                continue
            analysis = lora_analysis.get(filename)
            compatible = (
                analysis.compatible_checkpoints if analysis else list(checkpoints)
            )
            await db.execute(
                """
                UPDATE lora_profiles
                SET compatible_checkpoints = ?
                WHERE filename = ?
                """,
                (dump_compatible_checkpoints(compatible), filename),
            )
            compatibility_updated += 1
            if not compatible:
                incompatible_loras += 1

        if new_loras > 0 or compatibility_updated > 0:
            await db.commit()

    return {
        "checkpoints": image_checkpoints if image_checkpoints else checkpoints,
        "checkpoints_all": checkpoints,
        "non_image_checkpoints": non_image_checkpoints,
        "samplers": samplers,
        "schedulers": schedulers,
        "lora_files": lora_files,
        "new_loras": new_loras,
        "compatibility_updated": compatibility_updated,
        "incompatible_loras": incompatible_loras,
        "checkpoint_arches": checkpoint_arches,
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
    checkpoint_arches, _ = build_lora_compatibility_snapshot(checkpoints, [])
    image_checkpoints, non_image_checkpoints = _split_checkpoints_by_image_capability(
        checkpoints, checkpoint_arches
    )
    return {
        "checkpoints": image_checkpoints if image_checkpoints else checkpoints,
        "checkpoints_all": checkpoints,
        "non_image_checkpoints": non_image_checkpoints,
        "checkpoint_arches": checkpoint_arches,
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


@router.get("/quality-profiles")
async def list_quality_profiles(request: Request) -> dict:
    """Return checkpoint-specific recommended quality parameter profiles."""
    client: ComfyUIClient = request.app.state.comfyui_client
    checkpoints = await client.get_models()
    samplers = await client.get_samplers()
    schedulers = await client.get_schedulers()
    checkpoint_arches, _ = build_lora_compatibility_snapshot(checkpoints, [])

    profiles: dict[str, dict[str, Any]] = {}
    for checkpoint in checkpoints:
        arch = checkpoint_arches.get(checkpoint, "Unknown")
        profile = _quality_profile_for_arch(arch, samplers, schedulers)
        profiles[checkpoint] = {
            "checkpoint": checkpoint,
            "architecture": arch,
            **profile,
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profiles": profiles,
    }
