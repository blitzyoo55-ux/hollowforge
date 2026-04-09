"""Dispatch comic still render jobs to the remote worker."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.animation_dispatch_service import _join_url


class ComicRenderDispatchError(RuntimeError):
    """Raised when a comic remote render job cannot be dispatched."""


def _parse_request_json(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        if not raw.strip():
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ComicRenderDispatchError(
                "Comic render job request_json is invalid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise ComicRenderDispatchError(
                "Comic render job request_json must be a JSON object"
            )
        return parsed
    raise ComicRenderDispatchError("Comic render job request_json must be a JSON object")


def _parse_loras(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    if isinstance(raw, str):
        if not raw.strip():
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ComicRenderDispatchError("Generation loras field is invalid JSON") from exc
        if not isinstance(parsed, list):
            raise ComicRenderDispatchError("Generation loras field must be a JSON array")
        return [dict(item) for item in parsed if isinstance(item, dict)]
    raise ComicRenderDispatchError("Generation loras field must be a JSON array")


def _build_comic_callback_url(job_id: str) -> str:
    base_url = settings.PUBLIC_API_BASE_URL.strip()
    if not base_url:
        raise ComicRenderDispatchError("HOLLOWFORGE_PUBLIC_API_BASE_URL is not configured")

    parsed = urlparse(base_url)
    scheme = (parsed.scheme or "").strip().lower()
    hostname = (parsed.hostname or "").strip().lower()
    if scheme not in {"http", "https"} or not hostname:
        raise ComicRenderDispatchError(
            "HOLLOWFORGE_PUBLIC_API_BASE_URL must be a valid http(s) URL"
        )

    callback_url = _join_url(
        base_url,
        f"/api/v1/comic/render-jobs/{job_id}/callback",
    )
    callback_parsed = urlparse(callback_url)
    if (callback_parsed.scheme or "").strip().lower() not in {"http", "https"} or not (
        callback_parsed.hostname or ""
    ).strip():
        raise ComicRenderDispatchError(
            "HOLLOWFORGE_PUBLIC_API_BASE_URL did not produce a valid comic callback URL"
        )
    return callback_url


def build_comic_remote_worker_payload(
    comic_render_job: dict[str, Any],
    generation: dict[str, Any],
    render_asset: dict[str, Any],
    panel_context: dict[str, Any],
) -> dict[str, Any]:
    request_json = _parse_request_json(comic_render_job.get("request_json"))
    request_json.setdefault("backend_family", "sdxl_still")
    request_json.setdefault("model_profile", "comic_panel_sdxl_v1")
    request_json["still_generation"] = {
        "prompt": generation.get("prompt"),
        "negative_prompt": generation.get("negative_prompt"),
        "checkpoint": generation.get("checkpoint"),
        "seed": generation.get("seed"),
        "loras": _parse_loras(generation.get("loras")),
        "steps": generation.get("steps"),
        "cfg": generation.get("cfg"),
        "width": generation.get("width"),
        "height": generation.get("height"),
        "sampler": generation.get("sampler"),
        "scheduler": generation.get("scheduler"),
        "clip_skip": generation.get("clip_skip"),
        "source_id": generation.get("source_id"),
    }
    comic_metadata = request_json.get("comic")
    request_json["comic"] = {
        **(comic_metadata if isinstance(comic_metadata, dict) else {}),
        "scene_panel_id": render_asset.get("scene_panel_id"),
        "render_asset_id": render_asset.get("id"),
        "character_version_id": panel_context.get("character_version_id"),
    }
    callback_token = settings.ANIMATION_CALLBACK_TOKEN or None
    callback_url = _build_comic_callback_url(str(comic_render_job["id"]))

    return {
        "hollowforge_job_id": comic_render_job["id"],
        "generation_id": generation["id"],
        "target_tool": comic_render_job["target_tool"],
        "executor_mode": comic_render_job["executor_mode"],
        "executor_key": comic_render_job["executor_key"],
        "request_json": request_json,
        "callback_url": callback_url,
        "callback_token": callback_token,
    }


async def dispatch_comic_render_job(
    comic_render_job: dict[str, Any],
    generation: dict[str, Any],
    render_asset: dict[str, Any],
    panel_context: dict[str, Any],
) -> dict[str, Any]:
    if not settings.ANIMATION_REMOTE_BASE_URL:
        raise ComicRenderDispatchError("HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL is not configured")

    payload = build_comic_remote_worker_payload(
        comic_render_job,
        generation,
        render_asset,
        panel_context,
    )
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
        raise ComicRenderDispatchError(
            f"Remote comic render worker request failed: {exc}"
        ) from exc
    except ValueError as exc:
        raise ComicRenderDispatchError(
            "Remote comic render worker returned invalid JSON"
        ) from exc

    if not isinstance(data, dict):
        raise ComicRenderDispatchError(
            "Remote comic render worker returned unexpected response type"
        )
    return data
