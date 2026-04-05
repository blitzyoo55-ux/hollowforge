"""Run the bounded stale animation reconciliation helper against a local backend."""

from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
LOCAL_BACKEND_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}
STALE_JOB_STATUSES = ("queued", "submitted", "processing")


class _WorkerJobUnreachable(RuntimeError):
    """Raised when the worker cannot be polled reliably."""


def _is_local_backend_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    scheme = (parsed.scheme or "").strip().lower()
    hostname = (parsed.hostname or "").strip().lower()
    return scheme in {"http", "https"} and hostname in LOCAL_BACKEND_HOSTNAMES


def _normalize_worker_output_path(output_url: str | None) -> str | None:
    if not isinstance(output_url, str):
        return None

    candidate = output_url.strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    path = parsed.path if parsed.scheme and parsed.netloc else candidate
    path = path.strip().lstrip("/")
    if path.startswith("data/"):
        path = path[len("data/") :]
    return path or None


def _print_summary(summary: dict[str, int]) -> None:
    for key in (
        "checked",
        "updated",
        "failed_restart",
        "completed",
        "cancelled",
        "skipped_unreachable",
    ):
        print(f"{key}: {int(summary.get(key) or 0)}")


def _required_bearer_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token.strip()}"} if token.strip() else {}


async def _load_stale_jobs(backend_client: httpx.AsyncClient) -> list[dict[str, Any]]:
    jobs_by_id: dict[str, dict[str, Any]] = {}
    for status in STALE_JOB_STATUSES:
        response = await backend_client.get(
            "/api/v1/animation/jobs",
            params={"status_filter": status, "limit": 500},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("Animation jobs list response must be a JSON array")
        for item in payload:
            if not isinstance(item, dict):
                continue
            job_id = str(item.get("id") or "").strip()
            if not job_id:
                continue
            jobs_by_id[job_id] = item
    return list(jobs_by_id.values())


async def _fetch_worker_job(
    worker_client: httpx.AsyncClient,
    job_id: str,
) -> dict[str, Any] | None:
    headers = {"Accept": "application/json"}
    if settings.ANIMATION_WORKER_API_TOKEN.strip():
        headers.update(_required_bearer_header(settings.ANIMATION_WORKER_API_TOKEN))

    try:
        response = await worker_client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    except httpx.RequestError as exc:
        raise _WorkerJobUnreachable(str(exc)) from exc

    if response.status_code == 404:
        return None
    if response.status_code in {401, 403, 408, 429, 500, 502, 503, 504}:
        raise _WorkerJobUnreachable(f"worker returned HTTP {response.status_code}")

    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Worker job response must be a JSON object")
    return payload


async def _post_callback(
    backend_client: httpx.AsyncClient,
    *,
    job_id: str,
    payload: dict[str, Any],
) -> None:
    headers = {"Accept": "application/json"}
    if settings.ANIMATION_CALLBACK_TOKEN.strip():
        headers.update(_required_bearer_header(settings.ANIMATION_CALLBACK_TOKEN))

    response = await backend_client.post(
        f"/api/v1/animation/jobs/{job_id}/callback",
        headers=headers,
        json=payload,
    )
    response.raise_for_status()


def _callback_payload_for_job(
    current_job: dict[str, Any],
    worker_job: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if worker_job is None:
        return (
            {
                "status": "failed",
                "external_job_id": current_job.get("external_job_id"),
                "external_job_url": current_job.get("external_job_url"),
                "error_message": "Worker restarted",
            },
            "failed_restart",
        )

    worker_status = str(worker_job.get("status") or "").strip().lower()
    if worker_status == "completed":
        output_path = _normalize_worker_output_path(
            (
                worker_job.get("output_url")
                if isinstance(worker_job.get("output_url"), str)
                else worker_job.get("output_path")
            )
        )
        return (
            {
                "status": "completed",
                "external_job_id": current_job.get("external_job_id"),
                "external_job_url": current_job.get("external_job_url"),
                "output_path": output_path,
                "error_message": "",
            },
            "completed",
        )

    if worker_status == "cancelled":
        return (
            {
                "status": "cancelled",
                "external_job_id": current_job.get("external_job_id"),
                "external_job_url": current_job.get("external_job_url"),
                "error_message": "",
            },
            "cancelled",
        )

    if worker_status == "failed":
        worker_error_message = worker_job.get("error_message")
        if not isinstance(worker_error_message, str) or not worker_error_message.strip():
            worker_error_message = current_job.get("error_message")
        return (
            {
                "status": "failed",
                "external_job_id": current_job.get("external_job_id"),
                "external_job_url": current_job.get("external_job_url"),
                "error_message": worker_error_message,
            },
            None,
        )

    return None, None


async def _reconcile_via_http(base_url: str) -> dict[str, int]:
    summary = {
        "checked": 0,
        "updated": 0,
        "failed_restart": 0,
        "completed": 0,
        "cancelled": 0,
        "skipped_unreachable": 0,
    }

    async with AsyncExitStack() as stack:
        backend_client = await stack.enter_async_context(
            httpx.AsyncClient(base_url=base_url, timeout=settings.ANIMATION_REMOTE_SUBMIT_TIMEOUT_SEC)
        )

        worker_client: httpx.AsyncClient | None = None
        worker_base_url = settings.ANIMATION_REMOTE_BASE_URL.strip()
        if worker_base_url:
            worker_client = await stack.enter_async_context(
                httpx.AsyncClient(
                    base_url=worker_base_url,
                    timeout=settings.ANIMATION_REMOTE_SUBMIT_TIMEOUT_SEC,
                )
            )

        stale_jobs = await _load_stale_jobs(backend_client)
        for current_job in stale_jobs:
            summary["checked"] += 1
            external_job_id = str(current_job.get("external_job_id") or "").strip()
            if not external_job_id:
                continue

            if worker_client is None:
                summary["skipped_unreachable"] += 1
                continue

            try:
                worker_job = await _fetch_worker_job(worker_client, external_job_id)
            except _WorkerJobUnreachable:
                summary["skipped_unreachable"] += 1
                continue

            callback_payload, terminal_key = _callback_payload_for_job(current_job, worker_job)
            if callback_payload is None:
                continue

            await _post_callback(
                backend_client,
                job_id=str(current_job["id"]),
                payload=callback_payload,
            )

            summary["updated"] += 1
            if terminal_key is not None:
                summary[terminal_key] += 1

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    try:
        if not _is_local_backend_url(args.base_url):
            raise RuntimeError(
                "reconcile_stale_animation_jobs only supports local backend URLs"
            )

        summary = asyncio.run(_reconcile_via_http(args.base_url.rstrip("/")))
        _print_summary(summary)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
