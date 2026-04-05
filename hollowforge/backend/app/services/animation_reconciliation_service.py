"""Reconcile stale remote animation jobs against worker state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.db import get_db
from app.services.sequence_repository import mark_shot_clip_ready_for_completed_job

_STALE_JOB_STATUSES = ("queued", "submitted", "processing")
_JOB_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


class _WorkerJobMissing(RuntimeError):
    """Raised when the worker no longer knows about a job id."""


class _WorkerJobUnreachable(RuntimeError):
    """Raised when the worker could not be contacted reliably."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _normalize_worker_output_path(output_url: str | None) -> str | None:
    if not isinstance(output_url, str):
        return None

    candidate = output_url.strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    path = parsed.path if parsed.scheme and parsed.netloc else candidate
    path = path.strip()
    if not path:
        return None

    path = path.lstrip("/")
    if path.startswith("data/"):
        path = path[len("data/") :]

    return path or None


async def _fetch_worker_job(
    worker_base_url: str,
    job_id: str,
) -> dict[str, Any] | None:
    request_url = f"{worker_base_url.rstrip('/')}/api/v1/jobs/{job_id}"
    headers = {"Accept": "application/json"}
    if settings.ANIMATION_WORKER_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.ANIMATION_WORKER_API_TOKEN}"

    timeout = httpx.Timeout(settings.ANIMATION_REMOTE_SUBMIT_TIMEOUT_SEC)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(request_url, headers=headers)
    except httpx.RequestError as exc:
        raise _WorkerJobUnreachable(f"{request_url}: {exc}") from exc

    if response.status_code == 404:
        return None

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _WorkerJobUnreachable(f"{request_url}: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise _WorkerJobUnreachable(f"{request_url}: invalid JSON") from exc

    if not isinstance(payload, dict):
        raise _WorkerJobUnreachable(f"{request_url}: unexpected response payload")
    return payload


async def _update_animation_job(
    db: Any,
    current: dict[str, Any],
    *,
    next_status: str,
    next_output_path: str | None = None,
    next_error_message: str | None | object = Ellipsis,
) -> None:
    now = _now_iso()
    current_status = str(current.get("status") or "")
    next_submitted_at = current.get("submitted_at")
    if next_status in {"submitted", "processing", "completed"} and not next_submitted_at:
        next_submitted_at = now

    next_completed_at = current.get("completed_at")
    if next_status == "completed" and not next_completed_at:
        next_completed_at = now

    resolved_error_message: str | None
    if next_error_message is Ellipsis:
        resolved_error_message = current.get("error_message")
    else:
        resolved_error_message = next_error_message

    await db.execute(
        """
        UPDATE animation_jobs
        SET status = ?,
            output_path = ?,
            error_message = ?,
            submitted_at = ?,
            completed_at = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            next_status,
            next_output_path if next_output_path is not None else current.get("output_path"),
            resolved_error_message,
            next_submitted_at,
            next_completed_at,
            now,
            current["id"],
        ),
    )

    candidate_id = current.get("candidate_id")
    if candidate_id:
        cursor = await db.execute(
            "SELECT id FROM animation_candidates WHERE id = ?",
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

    if next_status == "completed":
        normalized_output_path = next_output_path if next_output_path is not None else current.get("output_path")
        if isinstance(normalized_output_path, str) and normalized_output_path.strip():
            clip_path = normalized_output_path.strip()
            await mark_shot_clip_ready_for_completed_job(
                animation_job_id=str(current["id"]),
                clip_path=clip_path,
            )


async def reconcile_stale_animation_jobs() -> dict[str, int]:
    """Poll stale remote-worker animation jobs and mirror terminal worker state."""
    worker_base_url = settings.ANIMATION_REMOTE_BASE_URL.strip()
    if not worker_base_url:
        raise RuntimeError("HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL is not configured")

    summary = {
        "checked": 0,
        "updated": 0,
        "failed_restart": 0,
        "completed": 0,
        "cancelled": 0,
        "skipped_unreachable": 0,
    }

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT *
            FROM animation_jobs
            WHERE executor_mode = 'remote_worker'
              AND status IN ('queued', 'submitted', 'processing')
              AND external_job_id IS NOT NULL
              AND trim(external_job_id) != ''
            ORDER BY updated_at ASC, created_at ASC
            """,
        )
        rows = await cursor.fetchall()

        for current in rows:
            summary["checked"] += 1
            external_job_id = str(current["external_job_id"]).strip()
            try:
                worker_job = await _fetch_worker_job(worker_base_url, external_job_id)
            except _WorkerJobUnreachable:
                summary["skipped_unreachable"] += 1
                continue

            if worker_job is None:
                await _update_animation_job(
                    db,
                    current,
                    next_status="failed",
                    next_error_message="Worker restarted",
                )
                summary["updated"] += 1
                summary["failed_restart"] += 1
                continue

            worker_status = str(worker_job.get("status") or "").strip().lower()
            if worker_status not in _JOB_TERMINAL_STATUSES:
                continue

            if worker_status == "completed":
                normalized_output_path = _normalize_worker_output_path(
                    (
                        worker_job.get("output_url")
                        if isinstance(worker_job.get("output_url"), str)
                        else worker_job.get("output_path")
                    )
                )
                await _update_animation_job(
                    db,
                    current,
                    next_status="completed",
                    next_output_path=normalized_output_path,
                    next_error_message=None,
                )
                summary["updated"] += 1
                summary["completed"] += 1
                continue

            if worker_status == "cancelled":
                await _update_animation_job(
                    db,
                    current,
                    next_status="cancelled",
                    next_error_message=None,
                )
                summary["updated"] += 1
                summary["cancelled"] += 1
                continue

            await _update_animation_job(
                db,
                current,
                next_status="failed",
                next_error_message="Worker restarted",
            )
            summary["updated"] += 1
            summary["failed_restart"] += 1

    return summary
