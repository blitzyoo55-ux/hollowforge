"""Animation orchestration endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.config import settings
from app.db import get_db
from app.models import (
    AnimationExecutorConfigResponse,
    AnimationJobCallbackPayload,
    AnimationJobCreate,
    AnimationJobDispatchResponse,
    AnimationPresetLaunchRequest,
    AnimationPresetLaunchResponse,
    AnimationPresetResponse,
    AnimationJobResponse,
    AnimationJobUpdate,
)
from app.services.animation_dispatch_service import (
    AnimationDispatchError,
    dispatch_to_remote_worker,
)
from app.services.sequence_repository import mark_shot_clip_ready_for_completed_job

router = APIRouter(prefix="/api/v1/animation", tags=["animation"])

_SUPPORTED_TARGET_TOOLS = [
    "dreamactor",
    "seedance",
    "wan_i2v",
    "hunyuan_avatar",
    "custom",
]

_DEFAULT_LTXV_PROMPT = (
    "subtle cinematic motion, slow camera drift, natural breathing, elegant hair and "
    "fabric movement, coherent body motion, clean timing"
)
_PORTRAIT_LOCKED_LTXV_PROMPT = (
    "locked portrait composition, same subject, preserve identity, preserve face, "
    "preserve hairstyle, preserve outfit, subject remains centered, camera locked, "
    "minimal natural breathing, subtle shoulder settle, faint fabric shimmer, no pose change"
)
_LTXV_2B_CHECKPOINT = "ltxv-2b-0.9.8-distilled-fp8.safetensors"
_LTX23_DISTILLED_CHECKPOINT = "ltx-2.3-22b-distilled.safetensors"
_LTXV_2B_FAST_REQUEST = {
    "backend_family": "ltxv",
    "model_profile": "ltxv_2b_fast",
    "checkpoint_name": _LTXV_2B_CHECKPOINT,
    "prompt": _DEFAULT_LTXV_PROMPT,
    "negative_prompt": settings.DEFAULT_NEGATIVE_PROMPT,
    "width": 768,
    "height": 512,
    "frames": 49,
    "fps": 12,
    "steps": 24,
    "cfg": 3.5,
    "seed": 42,
    "motion_strength": 0.55,
    "sampler_name": "euler",
    "max_shift": 2.05,
    "base_shift": 0.95,
    "stretch": True,
    "terminal": 0.1,
}
_LTXV_PORTRAIT_LOCKED_REQUEST = {
    "backend_family": "ltxv",
    "model_profile": "ltxv_2b_fast",
    "checkpoint_name": _LTXV_2B_CHECKPOINT,
    "prompt": _PORTRAIT_LOCKED_LTXV_PROMPT,
    "negative_prompt": (
        "child, teen, underage, school uniform, text, logo, watermark, blurry, "
        "lowres, deformed, cropped face, identity drift, different person, face morph, "
        "pose change, arm reposition, hand drift, finger morph, camera motion, zoom, "
        "pan, tilt, outfit change"
    ),
    "width": 512,
    "height": 768,
    "frames": 25,
    "fps": 10,
    "steps": 32,
    "cfg": 4.2,
    "seed": 42,
    "motion_strength": 0.18,
    "sampler_name": "euler",
    "max_shift": 1.35,
    "base_shift": 0.55,
    "stretch": False,
    "terminal": 0.05,
    "image_compression": 15,
}
_LTXV_CHARACTER_LOCK_V2_REQUEST = {
    "backend_family": "ltxv",
    "model_profile": "ltxv_2b_fast",
    "checkpoint_name": _LTXV_2B_CHECKPOINT,
    "inherit_generation_prompt": True,
    "prompt": (
        "same anime illustration style, preserve original character identity, preserve "
        "original face, preserve original hairstyle, preserve original outfit, same framing, "
        "same background, only subtle blink, slight breathing, faint fabric shimmer, no pose change"
    ),
    "negative_prompt": (
        "child, teen, underage, school uniform, text, logo, watermark, blurry, lowres, "
        "deformed, cropped face, realistic photo, live action, different art style, "
        "identity drift, different person, face morph, facial structure drift, hairstyle change, "
        "hair color change, pose change, arm reposition, hand drift, finger morph, camera motion, "
        "zoom, pan, tilt, outfit change"
    ),
    "width": 512,
    "height": 768,
    "frames": 13,
    "fps": 8,
    "steps": 40,
    "cfg": 4.0,
    "seed": 42,
    "motion_strength": 0.08,
    "sampler_name": "euler",
    "max_shift": 1.0,
    "base_shift": 0.35,
    "stretch": False,
    "terminal": 0.02,
    "image_compression": 5,
}
_LTX23_PORTRAIT_LOCKED_REQUEST = {
    "backend_family": "ltxv",
    "model_profile": "ltx23_distilled_quality",
    "checkpoint_name": _LTX23_DISTILLED_CHECKPOINT,
    "prompt": (
        "locked portrait composition, same subject, preserve identity, preserve face, "
        "preserve hairstyle, preserve outfit, same camera, same crop, subject remains "
        "centered, camera locked, only subtle breathing, faint shoulder settle, slight "
        "hair shimmer, no pose change, no framing change"
    ),
    "negative_prompt": (
        "child, teen, underage, school uniform, text, logo, watermark, blurry, "
        "lowres, deformed, cropped face, identity drift, different person, face morph, "
        "facial structure drift, hairstyle change, pose change, arm reposition, hand drift, "
        "finger morph, camera motion, zoom, pan, tilt, outfit change"
    ),
    "width": 512,
    "height": 768,
    "frames": 17,
    "fps": 8,
    "steps": 36,
    "cfg": 4.0,
    "seed": 42,
    "motion_strength": 0.1,
    "sampler_name": "euler",
    "max_shift": 1.1,
    "base_shift": 0.4,
    "stretch": False,
    "terminal": 0.03,
    "image_compression": 10,
}
_SDXL_IPADAPTER_MICROANIM_V1_REQUEST = {
    "backend_family": "sdxl_ipadapter",
    "model_profile": "sdxl_ipadapter_microanim_v1",
    "inherit_generation_prompt": True,
    "prompt": (
        "same anime illustration style, preserve original character identity, preserve "
        "original face, preserve original hairstyle, preserve original outfit, same framing, "
        "same background, only subtle blink, slight breathing, faint fabric shimmer, no pose change"
    ),
    "negative_prompt": (
        "child, teen, underage, school uniform, text, logo, watermark, blurry, lowres, "
        "deformed, cropped face, realistic photo, live action, different art style, "
        "identity drift, different person, face morph, facial structure drift, hairstyle change, "
        "hair color change, pose change, arm reposition, hand drift, finger morph, camera motion, "
        "zoom, pan, tilt, outfit change"
    ),
    "width": 512,
    "height": 768,
    "frames": 7,
    "fps": 6,
    "steps": 28,
    "cfg": 4.5,
    "seed": 42,
    "denoise": 0.12,
    "sampler_name": "dpmpp_2m",
    "scheduler": "karras",
    "ipadapter_weight": 0.95,
    "ipadapter_weight_type": "linear",
    "ipadapter_start_at": 0.0,
    "ipadapter_end_at": 1.0,
    "embeds_scaling": "K+mean(V) w/ C penalty",
    "upscale_method": "lanczos",
    "crop": "center",
}
_SDXL_IPADAPTER_MICROANIM_V2_REQUEST = {
    "backend_family": "sdxl_ipadapter",
    "model_profile": "sdxl_ipadapter_microanim_v2",
    "inherit_generation_prompt": True,
    "prompt": (
        "same anime illustration style, preserve original character identity, preserve "
        "original face, preserve original hairstyle, preserve original outfit, same framing, "
        "same background, micro-expression only, micro head settle only, delicate hair sway only, "
        "subtle breathing only, no pose change, no camera change"
    ),
    "negative_prompt": (
        "child, teen, underage, school uniform, text, logo, watermark, blurry, lowres, "
        "deformed, cropped face, realistic photo, live action, different art style, "
        "identity drift, different person, face morph, facial structure drift, hairstyle change, "
        "hair color change, pose change, arm reposition, hand drift, finger morph, camera motion, "
        "zoom, pan, tilt, outfit change"
    ),
    "width": 512,
    "height": 768,
    "frames": 9,
    "fps": 7,
    "steps": 30,
    "cfg": 4.8,
    "seed": 42,
    "denoise": 0.145,
    "sampler_name": "dpmpp_2m",
    "scheduler": "karras",
    "ipadapter_weight": 0.96,
    "ipadapter_weight_type": "linear",
    "ipadapter_start_at": 0.0,
    "ipadapter_end_at": 1.0,
    "embeds_scaling": "K+mean(V) w/ C penalty",
    "upscale_method": "lanczos",
    "crop": "center",
    "micro_motion_plan": [
        {
            "prompt": "eyes open, neutral expression, shoulders settled, hair resting close to neck",
            "denoise": 0.13,
        },
        {
            "prompt": "tiny inhale, faint chest lift, chin settling forward by a few millimeters, eyes open",
            "denoise": 0.14,
        },
        {
            "prompt": "eyes softening, lower eyelids lifting slightly, tiny hair sway near jawline",
            "denoise": 0.15,
        },
        {
            "prompt": "gentle blink beginning, same face shape, same mouth, same posture, slight collar shimmer",
            "denoise": 0.16,
        },
        {
            "prompt": "soft blink completed, slight head settle, same framing, same character, no body reposition",
            "denoise": 0.17,
        },
        {
            "prompt": "eyes reopening, tiny exhale, shoulders easing down, small hair sway near cheek",
            "denoise": 0.16,
        },
        {
            "prompt": "eyes open, micro confident expression, subtle breathing, same posture, same framing",
            "denoise": 0.15,
        },
        {
            "prompt": "eyes open, nearly still, faint reflective shimmer on outfit, hair settling back",
            "denoise": 0.14,
        },
        {
            "prompt": "eyes open, neutral expression, shoulders settled, hair resting close to neck",
            "denoise": 0.13,
        },
    ],
}
_BUILTIN_ANIMATION_PRESETS = {
    "sdxl_ipadapter_microanim_v2": AnimationPresetResponse(
        id="sdxl_ipadapter_microanim_v2",
        name="Local SDXL IPAdapter Micro-Anim v2",
        description=(
            "Identity-first local fallback with a stronger micro-motion plan for blink, "
            "head settle, breathing, and gentle hair sway."
        ),
        target_tool="custom",
        backend_family="sdxl_ipadapter",
        model_profile="sdxl_ipadapter_microanim_v2",
        request_json=dict(_SDXL_IPADAPTER_MICROANIM_V2_REQUEST),
    ),
    "sdxl_ipadapter_microanim_v1": AnimationPresetResponse(
        id="sdxl_ipadapter_microanim_v1",
        name="Local SDXL IPAdapter Micro-Anim v1",
        description=(
            "Identity-first local fallback using the source SDXL checkpoint, an IPAdapter "
            "reference image, and a short frame sequence rendered into MP4."
        ),
        target_tool="custom",
        backend_family="sdxl_ipadapter",
        model_profile="sdxl_ipadapter_microanim_v1",
        request_json=dict(_SDXL_IPADAPTER_MICROANIM_V1_REQUEST),
    ),
    "ltxv_character_lock_v2": AnimationPresetResponse(
        id="ltxv_character_lock_v2",
        name="Local LTXV Character Lock v2",
        description=(
            "More conservative portrait preset that inherits the original generation prompt "
            "to better preserve anime style and subject identity."
        ),
        target_tool="custom",
        backend_family="ltxv",
        model_profile="ltxv_2b_fast",
        request_json=dict(_LTXV_CHARACTER_LOCK_V2_REQUEST),
    ),
    "ltxv_portrait_locked": AnimationPresetResponse(
        id="ltxv_portrait_locked",
        name="Local LTXV Portrait Locked",
        description=(
            "Portrait-preserving image-to-video preset with lower motion and stronger "
            "identity lock for favorite review passes."
        ),
        target_tool="custom",
        backend_family="ltxv",
        model_profile="ltxv_2b_fast",
        request_json=dict(_LTXV_PORTRAIT_LOCKED_REQUEST),
    ),
    "ltxv_2b_fast": AnimationPresetResponse(
        id="ltxv_2b_fast",
        name="Local LTXV 2B Fast",
        description=(
            "Fast first-pass image-to-video preset for the local ComfyUI animation worker."
        ),
        target_tool="custom",
        backend_family="ltxv",
        model_profile="ltxv_2b_fast",
        request_json=dict(_LTXV_2B_FAST_REQUEST),
    ),
    "ltx23_portrait_locked": AnimationPresetResponse(
        id="ltx23_portrait_locked",
        name="Local LTX-2.3 Portrait Locked (Experimental)",
        description=(
            "Higher-quality portrait image-to-video preset using the LTX-2.3 distilled "
            "checkpoint. On this local Mac it may fail with MPS out-of-memory."
        ),
        target_tool="custom",
        backend_family="ltxv",
        model_profile="ltx23_distilled_quality",
        request_json=dict(_LTX23_PORTRAIT_LOCKED_REQUEST),
    ),
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json_object(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _get_animation_preset_or_404(preset_id: str) -> AnimationPresetResponse:
    preset = _BUILTIN_ANIMATION_PRESETS.get(preset_id)
    if preset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Animation preset {preset_id} not found",
        )
    return preset.model_copy(deep=True)


def _merge_request_json_payload(
    existing_raw: Any,
    incoming: dict[str, Any] | None,
) -> str | None:
    if incoming is None:
        return existing_raw

    merged = _parse_json_object(existing_raw) or {}
    if isinstance(merged.get("sequence"), dict) and isinstance(incoming.get("sequence"), dict):
        sequence_payload = dict(merged["sequence"])
        sequence_payload.update(incoming["sequence"])
        merged["sequence"] = sequence_payload

    for key, value in incoming.items():
        if key == "sequence" and isinstance(merged.get("sequence"), dict):
            continue
        merged[key] = value
    return json.dumps(merged, ensure_ascii=False)


def _build_preset_request_json(
    preset: AnimationPresetResponse,
    overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    request_json = dict(preset.request_json)
    for key, value in (overrides or {}).items():
        if value is None:
            continue
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                continue
            request_json[key] = trimmed
            continue
        request_json[key] = value
    if not str(request_json.get("negative_prompt") or "").strip():
        request_json["negative_prompt"] = settings.DEFAULT_NEGATIVE_PROMPT
    request_json["backend_family"] = preset.backend_family
    request_json["model_profile"] = preset.model_profile
    return request_json


def _row_to_animation_job(row: dict[str, Any]) -> AnimationJobResponse:
    return AnimationJobResponse(
        id=row["id"],
        candidate_id=row.get("candidate_id"),
        generation_id=row["generation_id"],
        publish_job_id=row.get("publish_job_id"),
        target_tool=row["target_tool"],
        executor_mode=row["executor_mode"],
        executor_key=row["executor_key"],
        status=row["status"],
        request_json=_parse_json_object(row.get("request_json")),
        external_job_id=row.get("external_job_id"),
        external_job_url=row.get("external_job_url"),
        output_path=row.get("output_path"),
        error_message=row.get("error_message"),
        submitted_at=row.get("submitted_at"),
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _candidate_status_for_job_status(job_status: str) -> str:
    return {
        "draft": "approved",
        "queued": "queued",
        "submitted": "queued",
        "processing": "processing",
        "completed": "completed",
        "failed": "approved",
        "cancelled": "approved",
    }.get(job_status, "approved")


def _should_preserve_terminal_animation_status(current_status: str, next_status: str) -> bool:
    if current_status == "completed":
        return next_status in {"failed", "queued", "submitted", "processing", "cancelled"}
    if current_status == "failed":
        return next_status in {"queued", "submitted", "processing", "completed"}
    if current_status == "cancelled":
        return next_status in {"queued", "submitted", "processing", "completed"}
    return False


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    value = authorization.strip()
    if value.lower().startswith(prefix):
        return value[len(prefix):].strip()
    return None


async def _require_generation(generation_id: str) -> dict[str, Any]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, image_path, checkpoint, prompt, created_at
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )
    return row


async def _require_animation_job(job_id: str) -> dict[str, Any]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM animation_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Animation job {job_id} not found",
        )
    return row


async def _apply_animation_job_update(
    db: Any,
    current: dict[str, Any],
    payload: AnimationJobUpdate | AnimationJobCallbackPayload,
    now: str,
) -> dict[str, Any]:
    next_status = payload.status or current["status"]
    next_external_job_id = (
        payload.external_job_id
        if payload.external_job_id is not None
        else current.get("external_job_id")
    )
    next_external_job_url = (
        payload.external_job_url
        if payload.external_job_url is not None
        else current.get("external_job_url")
    )
    next_output_path = (
        payload.output_path
        if payload.output_path is not None
        else current.get("output_path")
    )
    next_error_message = (
        payload.error_message
        if payload.error_message is not None
        else current.get("error_message")
    )
    next_request_json = _merge_request_json_payload(current.get("request_json"), payload.request_json)
    next_submitted_at = current.get("submitted_at")
    if next_status in {"submitted", "processing", "completed"} and not next_submitted_at:
        next_submitted_at = now
    next_completed_at = current.get("completed_at")
    if next_status == "completed" and not next_completed_at:
        next_completed_at = now

    await db.execute(
        """
        UPDATE animation_jobs
        SET status = ?,
            request_json = ?,
            external_job_id = ?,
            external_job_url = ?,
            output_path = ?,
            error_message = ?,
            submitted_at = ?,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            next_status,
            next_request_json,
            next_external_job_id,
            next_external_job_url,
            next_output_path,
            next_error_message,
            next_submitted_at,
            next_completed_at,
            now,
            current["id"],
        ),
    )

    candidate_id = current.get("candidate_id")
    if candidate_id:
        cursor = await db.execute(
            "SELECT * FROM animation_candidates WHERE id = ?",
            (candidate_id,),
        )
        candidate = await cursor.fetchone()
        if candidate is not None:
            await db.execute(
                """
                UPDATE animation_candidates
                SET status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    _candidate_status_for_job_status(next_status),
                    now,
                    candidate_id,
                ),
            )

    await db.commit()
    cursor = await db.execute(
        "SELECT * FROM animation_jobs WHERE id = ?",
        (current["id"],),
    )
    updated_row = await cursor.fetchone()
    if updated_row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update animation job",
        )

    clip_ready_path = None
    if next_status == "completed":
        if isinstance(next_output_path, str) and next_output_path.strip():
            clip_ready_path = next_output_path.strip()
        elif isinstance(next_external_job_url, str) and next_external_job_url.strip():
            clip_ready_path = next_external_job_url.strip()
    if clip_ready_path is not None:
        await mark_shot_clip_ready_for_completed_job(
            animation_job_id=current["id"],
            clip_path=clip_ready_path,
        )
    return updated_row


@router.get("/executor-config", response_model=AnimationExecutorConfigResponse)
async def get_animation_executor_config() -> AnimationExecutorConfigResponse:
    mode = settings.ANIMATION_EXECUTOR_MODE
    remote_base_url = settings.ANIMATION_REMOTE_BASE_URL or None
    managed_provider = (
        settings.ANIMATION_MANAGED_PROVIDER
        if mode == "managed_api"
        else None
    )
    preferred_flow = (
        "split_remote_worker"
        if mode == "remote_worker"
        else ("local_fallback" if mode == "local" else "managed_api_optional")
    )
    return AnimationExecutorConfigResponse(
        mode=mode,
        executor_key=settings.ANIMATION_EXECUTOR_KEY,
        remote_base_url=remote_base_url,
        managed_provider=managed_provider,
        supports_direct_submit=bool(remote_base_url),
        preferred_flow=preferred_flow,
        supported_target_tools=_SUPPORTED_TARGET_TOOLS,
    )


@router.get("/presets", response_model=list[AnimationPresetResponse])
async def list_animation_presets() -> list[AnimationPresetResponse]:
    return [preset.model_copy(deep=True) for preset in _BUILTIN_ANIMATION_PRESETS.values()]


@router.get("/jobs", response_model=list[AnimationJobResponse])
async def list_animation_jobs(
    status_filter: str | None = Query(default=None),
    candidate_id: str | None = Query(default=None),
    generation_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AnimationJobResponse]:
    clauses: list[str] = []
    params: list[Any] = []

    if status_filter:
        clauses.append("status = ?")
        params.append(status_filter)
    if candidate_id:
        clauses.append("candidate_id = ?")
        params.append(candidate_id)
    if generation_id:
        clauses.append("generation_id = ?")
        params.append(generation_id)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT *
            FROM animation_jobs
            {where_sql}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (*params, limit),
        )
        rows = await cursor.fetchall()

    return [_row_to_animation_job(row) for row in rows]


@router.get("/jobs/{job_id}", response_model=AnimationJobResponse)
async def get_animation_job(job_id: str) -> AnimationJobResponse:
    row = await _require_animation_job(job_id)
    return _row_to_animation_job(row)


@router.post("/jobs", response_model=AnimationJobResponse, status_code=status.HTTP_201_CREATED)
async def create_animation_job(payload: AnimationJobCreate) -> AnimationJobResponse:
    if not payload.candidate_id and not payload.generation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="candidate_id or generation_id is required",
        )

    now = _now_iso()
    candidate: dict[str, Any] | None = None

    async with get_db() as db:
        if payload.candidate_id:
            cursor = await db.execute(
                "SELECT * FROM animation_candidates WHERE id = ?",
                (payload.candidate_id,),
            )
            candidate = await cursor.fetchone()
            if candidate is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Animation candidate {payload.candidate_id} not found",
                )
            if candidate["status"] == "rejected":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rejected animation candidates cannot be queued",
                )

        generation_id = payload.generation_id or (candidate["generation_id"] if candidate else None)
        if generation_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="generation_id could not be resolved",
            )

        if payload.generation_id and candidate and payload.generation_id != candidate["generation_id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="generation_id does not match candidate generation",
            )

        await _require_generation(generation_id)

        publish_job_id = payload.publish_job_id
        if publish_job_id is None and candidate is not None:
            publish_job_id = candidate.get("publish_job_id")

        target_tool = (
            payload.target_tool
            or (candidate["target_tool"] if candidate else None)
            or settings.PUBLISH_DEFAULT_ANIMATION_TOOL
        )
        executor_mode = payload.executor_mode or settings.ANIMATION_EXECUTOR_MODE
        executor_key = payload.executor_key or settings.ANIMATION_EXECUTOR_KEY
        request_json = (
            json.dumps(payload.request_json, ensure_ascii=False)
            if payload.request_json is not None
            else None
        )
        job_id = str(uuid4())

        await db.execute(
            """
            INSERT INTO animation_jobs (
                id,
                candidate_id,
                generation_id,
                publish_job_id,
                target_tool,
                executor_mode,
                executor_key,
                status,
                request_json,
                external_job_id,
                external_job_url,
                output_path,
                error_message,
                submitted_at,
                completed_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                job_id,
                payload.candidate_id,
                generation_id,
                publish_job_id,
                target_tool,
                executor_mode,
                executor_key,
                payload.status,
                request_json,
                now,
                now,
            ),
        )

        if candidate is not None:
            approved_at = candidate.get("approved_at") or now
            await db.execute(
                """
                UPDATE animation_candidates
                SET status = ?,
                    approved_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    _candidate_status_for_job_status(payload.status),
                    approved_at,
                    now,
                    candidate["id"],
                ),
            )

        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM animation_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create animation job",
        )
    return _row_to_animation_job(row)


@router.post(
    "/presets/{preset_id}/launch",
    response_model=AnimationPresetLaunchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def launch_animation_preset(
    preset_id: str,
    payload: AnimationPresetLaunchRequest,
) -> AnimationPresetLaunchResponse:
    preset = _get_animation_preset_or_404(preset_id)
    request_json = _build_preset_request_json(preset, payload.request_overrides)

    created_job = await create_animation_job(
        AnimationJobCreate(
            candidate_id=payload.candidate_id,
            generation_id=payload.generation_id,
            publish_job_id=payload.publish_job_id,
            target_tool=preset.target_tool,
            executor_mode=payload.executor_mode,
            executor_key=payload.executor_key,
            status="queued",
            request_json=request_json,
        )
    )

    dispatch_result: AnimationJobDispatchResponse | None = None
    dispatch_error: str | None = None
    if payload.dispatch_immediately:
        try:
            dispatch_result = await dispatch_animation_job(created_job.id)
        except HTTPException as exc:
            detail = exc.detail
            dispatch_error = detail if isinstance(detail, str) else str(detail)

    return AnimationPresetLaunchResponse(
        preset=preset,
        animation_job=dispatch_result.animation_job if dispatch_result else created_job,
        dispatch=dispatch_result,
        dispatch_error=dispatch_error,
    )


@router.post(
    "/jobs/{job_id}/dispatch",
    response_model=AnimationJobDispatchResponse,
)
async def dispatch_animation_job(job_id: str) -> AnimationJobDispatchResponse:
    current = await _require_animation_job(job_id)
    if current["status"] in {"submitted", "processing", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Animation job {job_id} is already {current['status']}",
        )

    generation = await _require_generation(current["generation_id"])

    try:
        remote_response = await dispatch_to_remote_worker(current, generation)
    except AnimationDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    remote_worker_job_id = None
    remote_worker_job_url = None
    if isinstance(remote_response.get("id"), str):
        remote_worker_job_id = remote_response["id"]
    if isinstance(remote_response.get("job_url"), str):
        remote_worker_job_url = remote_response["job_url"]
    elif isinstance(remote_response.get("external_job_url"), str):
        remote_worker_job_url = remote_response["external_job_url"]

    callback_payload = AnimationJobCallbackPayload(
        status=str(remote_response.get("status") or "submitted"),
        external_job_id=remote_worker_job_id,
        external_job_url=remote_worker_job_url,
    )

    async with get_db() as db:
        updated_row = await _apply_animation_job_update(db, current, callback_payload, _now_iso())

    return AnimationJobDispatchResponse(
        animation_job=_row_to_animation_job(updated_row),
        dispatch_mode=updated_row["executor_mode"],
        remote_request_accepted=True,
        remote_worker_job_id=remote_worker_job_id,
        remote_worker_job_url=remote_worker_job_url,
    )


@router.patch("/jobs/{job_id}", response_model=AnimationJobResponse)
async def update_animation_job(
    job_id: str,
    payload: AnimationJobUpdate,
) -> AnimationJobResponse:
    current = await _require_animation_job(job_id)
    async with get_db() as db:
        updated_row = await _apply_animation_job_update(db, current, payload, _now_iso())
    return _row_to_animation_job(updated_row)


@router.post("/jobs/{job_id}/callback", response_model=AnimationJobResponse)
async def callback_animation_job(
    job_id: str,
    payload: AnimationJobCallbackPayload,
    authorization: str | None = Header(default=None),
) -> AnimationJobResponse:
    expected_token = settings.ANIMATION_CALLBACK_TOKEN
    if expected_token:
        actual_token = _extract_bearer_token(authorization)
        if actual_token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid animation callback token",
            )

    current = await _require_animation_job(job_id)
    next_status = payload.status or current["status"]
    if _should_preserve_terminal_animation_status(current["status"], next_status):
        return _row_to_animation_job(current)

    async with get_db() as db:
        updated_row = await _apply_animation_job_update(db, current, payload, _now_iso())
    return _row_to_animation_job(updated_row)
