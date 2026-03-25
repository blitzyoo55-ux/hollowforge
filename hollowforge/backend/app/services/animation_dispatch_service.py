"""Dispatch animation jobs to an external animation worker."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


class AnimationDispatchError(RuntimeError):
    """Raised when an animation job cannot be dispatched to the remote worker."""


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _build_public_data_url(rel_path: str) -> str:
    if not rel_path:
        raise AnimationDispatchError("Missing relative asset path for public URL build")
    return _join_url(settings.PUBLIC_API_BASE_URL, f"/data/{rel_path}")


def _preserve_nested_sequence_metadata(
    request_json: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if request_json is None:
        return None

    sequence_keys = (
        "sequence_run_id",
        "sequence_shot_id",
        "content_mode",
        "executor_profile_id",
    )
    nested = request_json.get("sequence")
    sequence_metadata = dict(nested) if isinstance(nested, dict) else {}
    for key in sequence_keys:
        value = request_json.get(key)
        if value is not None and key not in sequence_metadata:
            sequence_metadata[key] = value
    if not sequence_metadata:
        return request_json

    normalized = dict(request_json)
    normalized["sequence"] = sequence_metadata
    return normalized


def build_remote_worker_payload(
    animation_job: dict[str, Any],
    generation: dict[str, Any],
) -> dict[str, Any]:
    image_path = generation.get("image_path")
    if not isinstance(image_path, str) or not image_path:
        raise AnimationDispatchError("Generation has no source image for animation dispatch")

    request_json = animation_job.get("request_json")
    parsed_request_json: dict[str, Any] | None = None
    if isinstance(request_json, str) and request_json.strip():
        try:
            parsed = json.loads(request_json)
        except json.JSONDecodeError as exc:
            raise AnimationDispatchError("Animation job request_json is invalid JSON") from exc
        if isinstance(parsed, dict):
            parsed_request_json = _preserve_nested_sequence_metadata(parsed)
    elif isinstance(request_json, dict):
        parsed_request_json = _preserve_nested_sequence_metadata(request_json)

    callback_token = settings.ANIMATION_CALLBACK_TOKEN or None
    callback_url = _join_url(
        settings.PUBLIC_API_BASE_URL,
        f"/api/v1/animation/jobs/{animation_job['id']}/callback",
    )

    return {
        "hollowforge_job_id": animation_job["id"],
        "candidate_id": animation_job.get("candidate_id"),
        "generation_id": animation_job["generation_id"],
        "publish_job_id": animation_job.get("publish_job_id"),
        "target_tool": animation_job["target_tool"],
        "executor_mode": animation_job["executor_mode"],
        "executor_key": animation_job["executor_key"],
        "source_image_url": _build_public_data_url(image_path),
        "generation_metadata": {
            "checkpoint": generation.get("checkpoint"),
            "prompt": generation.get("prompt"),
            "created_at": generation.get("created_at"),
        },
        "request_json": parsed_request_json,
        "callback_url": callback_url,
        "callback_token": callback_token,
    }


async def dispatch_to_remote_worker(
    animation_job: dict[str, Any],
    generation: dict[str, Any],
) -> dict[str, Any]:
    if not settings.ANIMATION_REMOTE_BASE_URL:
        raise AnimationDispatchError("HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL is not configured")

    payload = build_remote_worker_payload(animation_job, generation)
    headers: dict[str, str] = {}
    if settings.ANIMATION_WORKER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.ANIMATION_WORKER_API_TOKEN}"

    timeout = httpx.Timeout(settings.ANIMATION_REMOTE_SUBMIT_TIMEOUT_SEC)
    submit_url = _join_url(settings.ANIMATION_REMOTE_BASE_URL, "/api/v1/jobs")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(submit_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise AnimationDispatchError(f"Remote animation worker request failed: {exc}") from exc
    except ValueError as exc:
        raise AnimationDispatchError("Remote animation worker returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise AnimationDispatchError("Remote animation worker returned unexpected response type")
    return data
