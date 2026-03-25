"""System health and status endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.db import get_db
from app.models import (
    ComfyUIConfigUpdate,
    PromptFactoryCheckpointPreferencesReplaceRequest,
    PromptFactoryCheckpointPreferencesResponse,
    PromptFactoryCheckpointPreferenceEntryResponse,
    SystemHealth,
    WatermarkSettings,
    WatermarkSettingsUpdate,
)
from app.services.prompt_factory_service import load_prompt_factory_checkpoint_preferences
from app.services.comfyui_client import ComfyUIClient
from app.services.model_compatibility import (
    build_lora_compatibility_snapshot,
    clear_model_compatibility_cache,
    dump_compatible_checkpoints,
)
from app.services.workflow_registry import get_workflow_lane_spec
from app.services.workflow_builder import QUALITY_UPSCALE_REQUIRED_NODES
from app.services.upscaler import (
    classify_checkpoint_upscale_profile,
    list_local_upscale_models,
    recommend_upscale_mode,
    recommend_upscale_model,
)

router = APIRouter(prefix="/api/v1/system", tags=["system"])

_NON_IMAGE_ARCHES = {"WAN-I2V-14B", "SVD-XT"}
_PROMPT_FACTORY_PREFERENCE_MODE_RANK = {
    "default": 0,
    "prefer": 1,
    "force": 2,
    "exclude": -1,
}


async def _fetch_model_inventory(
    client: ComfyUIClient,
) -> tuple[list[str], list[str], list[str], list[str]]:
    checkpoints, samplers, schedulers, lora_files = await asyncio.gather(
        client.get_models(),
        client.get_samplers(),
        client.get_schedulers(),
        client.get_lora_files(),
    )
    return checkpoints, samplers, schedulers, lora_files


def _display_name_from_lora_filename(filename: str) -> str:
    display_name = filename.removesuffix(".safetensors")
    return display_name.replace("_", " ")


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


def _normalize_prompt_factory_preference_entry(
    checkpoint: str,
    *,
    available: bool,
    architecture: str | None,
    favorite_count: int,
    mode: str = "default",
    priority_boost: int = 0,
    notes: str | None = None,
    updated_at: str | None = None,
) -> PromptFactoryCheckpointPreferenceEntryResponse:
    return PromptFactoryCheckpointPreferenceEntryResponse(
        checkpoint=checkpoint,
        available=available,
        architecture=architecture,
        favorite_count=favorite_count,
        mode=mode if mode in _PROMPT_FACTORY_PREFERENCE_MODE_RANK else "default",
        priority_boost=priority_boost,
        notes=notes,
        updated_at=updated_at,
    )


async def _load_prompt_factory_favorite_counts() -> dict[str, int]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT checkpoint, COUNT(*) AS cnt
            FROM generations
            WHERE is_favorite = 1
            GROUP BY checkpoint
            """
        )
        rows = await cursor.fetchall()

    favorite_counts: dict[str, int] = {}
    for row in rows:
        checkpoint = row.get("checkpoint")
        if isinstance(checkpoint, str) and checkpoint.strip():
            favorite_counts[checkpoint.strip()] = int(row.get("cnt") or 0)
    return favorite_counts


async def _build_prompt_factory_checkpoint_preferences_response(
    request: Request,
) -> PromptFactoryCheckpointPreferencesResponse:
    client: ComfyUIClient = request.app.state.comfyui_client
    checkpoints = await client.get_models()
    checkpoint_arches, _ = build_lora_compatibility_snapshot(checkpoints, [])
    image_checkpoints, _ = _split_checkpoints_by_image_capability(
        checkpoints, checkpoint_arches
    )
    available_checkpoints = image_checkpoints if image_checkpoints else checkpoints
    available_checkpoint_set = set(available_checkpoints)
    favorite_counts = await _load_prompt_factory_favorite_counts()
    preferences = await load_prompt_factory_checkpoint_preferences()

    checkpoint_names = available_checkpoint_set | set(preferences.keys())
    entries: list[PromptFactoryCheckpointPreferenceEntryResponse] = []
    for checkpoint in checkpoint_names:
        preference = preferences.get(checkpoint)
        entries.append(
            _normalize_prompt_factory_preference_entry(
                checkpoint,
                available=checkpoint in available_checkpoint_set,
                architecture=checkpoint_arches.get(checkpoint),
                favorite_count=favorite_counts.get(checkpoint, 0),
                mode=preference.mode if preference else "default",
                priority_boost=preference.priority_boost if preference else 0,
                notes=preference.notes if preference else None,
                updated_at=preference.updated_at if preference else None,
            )
        )

    entries.sort(
        key=lambda entry: (
            -_PROMPT_FACTORY_PREFERENCE_MODE_RANK.get(entry.mode, 0),
            -entry.priority_boost,
            -entry.favorite_count,
            entry.checkpoint.lower(),
        )
    )
    return PromptFactoryCheckpointPreferencesResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        entries=entries,
    )


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
    sdxl_defaults = get_workflow_lane_spec("sdxl_illustrious").defaults
    return {
        "applicable": True,
        "profile_name": "SDXL Illustrious Production",
        "description": "Dual-encoder production defaults aligned to HollowForge favorites and current SDXL illustration output.",
        "params": {
            "steps": sdxl_defaults["steps"],
            "cfg": sdxl_defaults["cfg"],
            "width": sdxl_defaults["width"],
            "height": sdxl_defaults["height"],
            "sampler": _pick_first_available(
                ["euler_ancestral", "euler", "dpmpp_2m"],
                samplers,
                "euler_ancestral",
            ),
            "scheduler": _pick_first_available(["normal", "karras"], schedulers, "normal"),
            "clip_skip": sdxl_defaults["clip_skip"],
        },
    }


def _prompt_template(
    template_id: str,
    name: str,
    text: str,
    description: str,
) -> dict[str, str]:
    return {
        "id": template_id,
        "name": name,
        "text": text,
        "description": description,
    }


def _prompt_templates_for_arch(architecture: str) -> dict[str, Any]:
    if architecture == "SD1.5":
        positive = [
            _prompt_template(
                "sd15-tag-character",
                "SD1.5 Tag Character",
                "masterpiece, best quality, 1girl, {subject}, {outfit}, {pose}, detailed face, detailed eyes, soft lighting, sharp focus, high detail",
                "Tag-heavy baseline for SD1.5 anime checkpoints. Keep tokens short and comma-separated.",
            ),
            _prompt_template(
                "sd15-studio-portrait",
                "SD1.5 Studio Portrait",
                "masterpiece, best quality, portrait, {subject}, {emotion}, clean background, studio light, skin detail, depth of field",
                "Stable portrait baseline with fewer concept tokens to reduce drift.",
            ),
        ]
        negative = [
            _prompt_template(
                "sd15-safe-cleanup",
                "SD1.5 Cleanup",
                "worst quality, low quality, lowres, blurry, bad anatomy, bad hands, extra fingers, missing fingers, deformed, text, watermark, logo, jpeg artifacts",
                "Default cleanup for anatomy and artifact suppression.",
            ),
            _prompt_template(
                "sd15-style-suppress",
                "SD1.5 Style Suppress",
                "flat lighting, washed colors, overexposed, underexposed, noisy background, duplicate face, distorted body, malformed limbs",
                "Use when style LoRA overpowers composition or tone.",
            ),
        ]
        return {
            "default_positive_template_id": "sd15-tag-character",
            "default_negative_template_id": "sd15-safe-cleanup",
            "positive_templates": positive,
            "negative_templates": negative,
            "guidance": [
                "SD1.5 usually responds best to compact tag sequences.",
                "Too many long natural-language clauses can reduce prompt adherence.",
            ],
        }

    if architecture == "FLUX":
        positive = [
            _prompt_template(
                "flux-natural-portrait",
                "FLUX Natural Portrait",
                "A high-detail portrait of {subject} in {scene}. Natural skin texture, realistic lighting, balanced contrast, shallow depth of field, 50mm lens look.",
                "Natural-language baseline for FLUX checkpoints.",
            ),
            _prompt_template(
                "flux-cinematic-scene",
                "FLUX Cinematic Scene",
                "A cinematic still of {subject} in {scene}, dramatic key light, volumetric atmosphere, rich color separation, fine texture detail, clean composition.",
                "Use complete sentences and concrete scene cues.",
            ),
        ]
        negative = [
            _prompt_template(
                "flux-light-negative",
                "FLUX Light Negative",
                "blurry, low detail, artifacts, deformed anatomy, extra limbs, text, watermark",
                "Keep negatives shorter on FLUX workflows to avoid over-constraint.",
            ),
            _prompt_template(
                "flux-composition-guard",
                "FLUX Composition Guard",
                "cluttered frame, subject cut off, duplicate body, distorted perspective, messy background",
                "Use when subject framing and geometry are unstable.",
            ),
        ]
        return {
            "default_positive_template_id": "flux-natural-portrait",
            "default_negative_template_id": "flux-light-negative",
            "positive_templates": positive,
            "negative_templates": negative,
            "guidance": [
                "FLUX generally prefers sentence-style prompts over long tag lists.",
                "If true CFG mode is used, negative prompt influence may differ from SDXL/SD1.5.",
            ],
        }

    # Default: SDXL-family and unknown image checkpoints
    positive = [
        _prompt_template(
            "sdxl-illustrious-core",
            "SDXL Illustrious Core",
            "masterpiece, best quality, 1girl, solo, {subject}, {outfit}, {pose}, {scene}, detailed eyes, glossy materials, controlled composition, dramatic lighting, sharp focus",
            "Tag-stack baseline for SDXL illustration production.",
        ),
        _prompt_template(
            "sdxl-lab451-editorial",
            "SDXL Lab-451 Editorial",
            "masterpiece, best quality, 1girl, solo, lab-451, {subject}, {outfit}, {scene}, containment design, reflective surfaces, restrained palette, editorial framing, premium material detail",
            "Production template for Lab-451 themed editorial variants.",
        ),
    ]
    negative = [
        _prompt_template(
            "sdxl-cleanup",
            "SDXL Cleanup",
            "lowres, blurry, bad anatomy, extra fingers, missing fingers, deformed hands, text, watermark, logo, jpeg artifacts, worst quality",
            "Default SDXL artifact suppression.",
        ),
        _prompt_template(
            "sdxl-overstyle-control",
            "SDXL Overstyle Control",
            "oversaturated, plastic skin, over-sharpened, noisy shadows, muddy details, duplicate subject, background clutter",
            "Use when LoRA stacking causes over-stylized or noisy results.",
        ),
    ]
    return {
        "default_positive_template_id": "sdxl-illustrious-core",
        "default_negative_template_id": "sdxl-cleanup",
        "positive_templates": positive,
        "negative_templates": negative,
        "guidance": [
            "Use concise comma-separated tag stacks for Illustrious / anime SDXL checkpoints.",
            "Lead with subject and composition, then append material and environment cues.",
        ],
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


def _row_to_watermark_settings(row: dict[str, Any]) -> WatermarkSettings:
    return WatermarkSettings(
        id=row.get("id", 1),
        enabled=bool(row.get("enabled", 0)),
        text=row.get("text") or "Lab-XX",
        position=row.get("position") or "bottom-right",
        opacity=row.get("opacity") if row.get("opacity") is not None else 0.6,
        font_size=row.get("font_size") if row.get("font_size") is not None else 36,
        padding=row.get("padding") if row.get("padding") is not None else 20,
        color=row.get("color") or "#FFFFFF",
        updated_at=row.get("updated_at")
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


@router.post("/sync")
async def sync_models(request: Request) -> dict:
    """Refresh models/LoRAs from ComfyUI and return current lists."""
    client: ComfyUIClient = request.app.state.comfyui_client
    client.invalidate_metadata_cache()
    clear_model_compatibility_cache()
    checkpoints, samplers, schedulers, lora_files = await _fetch_model_inventory(client)
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
        cursor = await db.execute(
            "SELECT filename, compatible_checkpoints FROM lora_profiles"
        )
        rows = await cursor.fetchall()
        existing_filenames = {row["filename"] for row in rows}
        existing_compatibility = {
            row["filename"]: row.get("compatible_checkpoints")
            for row in rows
        }
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        insert_records: list[tuple[str, str, str, str, float, str | None, str]] = []
        update_records: list[tuple[str | None, str]] = []

        for filename in lora_files:
            analysis = lora_analysis.get(filename)
            compatible = analysis.compatible_checkpoints if analysis else list(checkpoints)
            compatible_payload = dump_compatible_checkpoints(compatible)
            if not compatible:
                incompatible_loras += 1

            if filename in existing_filenames:
                if existing_compatibility.get(filename) != compatible_payload:
                    update_records.append((compatible_payload, filename))
                    compatibility_updated += 1
                continue

            category = analysis.category if analysis else "style"
            default_strength = analysis.default_strength if analysis else 0.5
            insert_records.append(
                (
                    str(uuid4()),
                    _display_name_from_lora_filename(filename),
                    filename,
                    category,
                    default_strength,
                    compatible_payload,
                    now,
                )
            )
            new_loras += 1
            compatibility_updated += 1

        if insert_records:
            await db.executemany(
                """
                INSERT INTO lora_profiles
                    (id, display_name, filename, category, default_strength, compatible_checkpoints, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                insert_records,
            )

        if update_records:
            await db.executemany(
                """
                UPDATE lora_profiles
                SET compatible_checkpoints = ?
                WHERE filename = ?
                """,
                update_records,
            )

        if insert_records or update_records:
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
    completed_generations = 0
    failed_generations = 0
    cancelled_generations = 0
    try:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT status, COUNT(*) AS cnt FROM generations GROUP BY status"
            )
            rows = await cursor.fetchall()
            counts = {row["status"]: row["cnt"] for row in rows}
            total_generations = sum(counts.values())
            completed_generations = counts.get("completed", 0)
            failed_generations = counts.get("failed", 0)
            cancelled_generations = counts.get("cancelled", 0)
            db_ok = True
    except Exception:
        pass

    status = "healthy" if (comfyui_ok and db_ok) else "degraded"
    return SystemHealth(
        status=status,
        comfyui_connected=comfyui_ok,
        db_ok=db_ok,
        total_generations=total_generations,
        completed_generations=completed_generations,
        failed_generations=failed_generations,
        cancelled_generations=cancelled_generations,
    )


@router.get("/comfyui")
async def comfyui_status(request: Request) -> dict:
    """Check ComfyUI connectivity."""
    client: ComfyUIClient = request.app.state.comfyui_client
    connected = await client.check_health()
    return {"connected": connected, "url": client.base_url}


@router.get("/watermark", response_model=WatermarkSettings)
async def get_watermark_settings() -> WatermarkSettings:
    """Fetch current watermark configuration."""
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO watermark_settings (id) VALUES (1)")
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM watermark_settings WHERE id = 1"
        )
        row = await cursor.fetchone()

    if row is None:
        return _row_to_watermark_settings({})
    return _row_to_watermark_settings(row)


@router.post("/watermark", response_model=WatermarkSettings)
async def update_watermark_settings(
    payload: WatermarkSettingsUpdate,
) -> WatermarkSettings:
    """Update watermark configuration."""
    text = payload.text.strip()
    async with get_db() as db:
        await db.execute("INSERT OR IGNORE INTO watermark_settings (id) VALUES (1)")
        await db.execute(
            """UPDATE watermark_settings
               SET enabled = ?, text = ?, position = ?, opacity = ?,
                   font_size = ?, padding = ?, color = ?,
                   updated_at = datetime('now')
               WHERE id = 1""",
            (
                int(payload.enabled),
                text or "Lab-XX",
                payload.position,
                payload.opacity,
                payload.font_size,
                payload.padding,
                payload.color,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM watermark_settings WHERE id = 1"
        )
        row = await cursor.fetchone()

    if row is None:
        return _row_to_watermark_settings({})
    return _row_to_watermark_settings(row)


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
    checkpoints, samplers, schedulers, lora_files = await _fetch_model_inventory(client)
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


@router.get(
    "/prompt-factory-checkpoint-preferences",
    response_model=PromptFactoryCheckpointPreferencesResponse,
)
async def get_prompt_factory_checkpoint_preferences(
    request: Request,
) -> PromptFactoryCheckpointPreferencesResponse:
    return await _build_prompt_factory_checkpoint_preferences_response(request)


@router.put(
    "/prompt-factory-checkpoint-preferences",
    response_model=PromptFactoryCheckpointPreferencesResponse,
)
async def replace_prompt_factory_checkpoint_preferences(
    payload: PromptFactoryCheckpointPreferencesReplaceRequest,
    request: Request,
) -> PromptFactoryCheckpointPreferencesResponse:
    seen: set[str] = set()
    normalized_rows: list[tuple[str, str, int, str | None, str]] = []
    now = datetime.now(timezone.utc).isoformat()

    for entry in payload.entries:
        checkpoint = entry.checkpoint.strip()
        if not checkpoint:
            continue
        if checkpoint in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate checkpoint preference payload: {checkpoint}",
            )
        seen.add(checkpoint)

        notes = entry.notes.strip() if isinstance(entry.notes, str) else None
        if notes == "":
            notes = None
        if entry.mode == "default" and entry.priority_boost == 0 and notes is None:
            continue
        normalized_rows.append(
            (
                checkpoint,
                entry.mode,
                entry.priority_boost,
                notes,
                now,
            )
        )

    async with get_db() as db:
        await db.execute("DELETE FROM prompt_factory_checkpoint_preferences")
        if normalized_rows:
            await db.executemany(
                """
                INSERT INTO prompt_factory_checkpoint_preferences
                    (checkpoint, mode, priority_boost, notes, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                normalized_rows,
            )
        await db.commit()

    return await _build_prompt_factory_checkpoint_preferences_response(request)


@router.get("/upscale-models")
async def list_upscale_models(request: Request, checkpoint: str | None = None) -> dict:
    """List available upscaler models from ComfyUI and local fallback paths."""
    client: ComfyUIClient = request.app.state.comfyui_client
    local_models = list_local_upscale_models()
    comfyui_models, quality_missing_nodes = await asyncio.gather(
        client.get_upscale_models(),
        client.missing_nodes(QUALITY_UPSCALE_REQUIRED_NODES)
        if settings.UPSCALE_QUALITY_ENABLED
        else asyncio.sleep(0, result=list(QUALITY_UPSCALE_REQUIRED_NODES)),
    )
    combined = sorted(
        set(comfyui_models) | set(local_models),
        key=str.lower,
    )
    recommended_model, recommended_profile = recommend_upscale_model(
        checkpoint,
        combined,
    )
    recommended_mode, recommended_mode_reason = recommend_upscale_mode(checkpoint)
    return {
        "upscale_models": combined,
        "comfyui_models": sorted(set(comfyui_models), key=str.lower),
        "local_models": sorted(set(local_models), key=str.lower),
        "recommended_model": recommended_model,
        "recommended_profile": (
            recommended_profile
            if checkpoint
            else classify_checkpoint_upscale_profile(None)
        ),
        "recommended_checkpoint": checkpoint,
        "recommended_mode": recommended_mode,
        "recommended_mode_reason": recommended_mode_reason,
        "safe_upscale_enabled": True,
        "safe_upscale_engine": (
            "comfyui" if settings.UPSCALE_SAFE_USE_COMFYUI else "cpu-fallback"
        ),
        "quality_upscale_enabled": settings.UPSCALE_QUALITY_ENABLED
        and not quality_missing_nodes,
        "quality_required_nodes": list(QUALITY_UPSCALE_REQUIRED_NODES),
        "quality_missing_nodes": quality_missing_nodes,
        "quality_upscale_reason": (
            None
            if settings.UPSCALE_QUALITY_ENABLED and not quality_missing_nodes
            else (
                "Quality upscale is disabled until the staged ComfyUI workflow is validated"
                if not settings.UPSCALE_QUALITY_ENABLED
                else "Missing ComfyUI nodes: " + ", ".join(quality_missing_nodes)
            )
        ),
    }


@router.get("/quality-profiles")
async def list_quality_profiles(request: Request) -> dict:
    """Return checkpoint-specific recommended quality parameter profiles."""
    client: ComfyUIClient = request.app.state.comfyui_client
    checkpoints, samplers, schedulers, _ = await _fetch_model_inventory(client)
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


@router.get("/prompt-templates")
async def list_prompt_templates(request: Request) -> dict:
    """Return checkpoint-specific positive/negative prompt templates."""
    client: ComfyUIClient = request.app.state.comfyui_client
    checkpoints = await client.get_models()
    checkpoint_arches, _ = build_lora_compatibility_snapshot(checkpoints, [])

    templates: dict[str, dict[str, Any]] = {}
    for checkpoint in checkpoints:
        arch = checkpoint_arches.get(checkpoint, "Unknown")
        templates[checkpoint] = {
            "checkpoint": checkpoint,
            "architecture": arch,
            **_prompt_templates_for_arch(arch),
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "variables": [
            {
                "token": "{subject}",
                "description": "Core subject identity (character/person/object).",
                "example": "futuristic android heroine",
            },
            {
                "token": "{scene}",
                "description": "Environment/background context.",
                "example": "neon-lit cyberpunk alley at night",
            },
            {
                "token": "{pose}",
                "description": "Body pose or camera framing cue.",
                "example": "waist-up portrait, looking at camera",
            },
            {
                "token": "{outfit}",
                "description": "Main wardrobe or material details.",
                "example": "black tactical jacket with reflective accents",
            },
            {
                "token": "{emotion}",
                "description": "Facial expression or mood keyword.",
                "example": "confident subtle smile",
            },
        ],
        "templates": templates,
    }
