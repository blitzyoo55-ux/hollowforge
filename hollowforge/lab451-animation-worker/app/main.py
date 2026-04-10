"""FastAPI app for the Lab451 animation worker."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import get_db, init_db, now_iso
from app.executors import build_executor
from app.models import (
    HollowForgeCallbackPayload,
    WorkerHealthResponse,
    WorkerJobCreate,
    WorkerJobResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _job_url(worker_job_id: str) -> str:
    return f"{settings.WORKER_PUBLIC_BASE_URL.rstrip('/')}/api/v1/jobs/{worker_job_id}"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    value = authorization.strip()
    if value.lower().startswith(prefix):
        return value[len(prefix):].strip()
    return None


def _require_api_token(authorization: str | None) -> None:
    expected = settings.WORKER_API_TOKEN
    if not expected:
        return
    actual = _extract_bearer_token(authorization)
    if actual != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid worker API token",
        )


def _parse_json_object(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _optional_text(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    return value or None


def _callback_output_path(raw: Any) -> str | None:
    value = _optional_text(raw)
    if value is None:
        return None

    parsed = urlparse(value)
    normalized = parsed.path if parsed.scheme or parsed.netloc else value
    if normalized.startswith("/data/"):
        return normalized[len("/data/") :]
    if normalized.startswith("data/"):
        return normalized[len("data/") :]
    return normalized.lstrip("/")


def _row_to_response(row: dict[str, Any]) -> WorkerJobResponse:
    return WorkerJobResponse(
        id=row["id"],
        hollowforge_job_id=row["hollowforge_job_id"],
        candidate_id=row.get("candidate_id"),
        generation_id=row["generation_id"],
        publish_job_id=row.get("publish_job_id"),
        target_tool=row["target_tool"],
        executor_mode=row["executor_mode"],
        executor_key=row["executor_key"],
        status=row["status"],
        source_image_url=_optional_text(row.get("source_image_url")),
        generation_metadata=_parse_json_object(row.get("generation_metadata")),
        request_json=_parse_json_object(row.get("request_json")),
        callback_url=row.get("callback_url"),
        external_job_id=row.get("external_job_id"),
        external_job_url=row.get("external_job_url"),
        output_url=row.get("output_url"),
        error_message=row.get("error_message"),
        submitted_at=row.get("submitted_at"),
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        job_url=_job_url(row["id"]),
    )


async def _notify_hollowforge(row: dict[str, Any], payload: HollowForgeCallbackPayload) -> None:
    callback_url = row.get("callback_url")
    if not isinstance(callback_url, str) or not callback_url:
        return

    headers: dict[str, str] = {}
    callback_token = row.get("callback_token")
    if isinstance(callback_token, str) and callback_token:
        headers["Authorization"] = f"Bearer {callback_token}"
    cf_access_client_id = settings.WORKER_CF_ACCESS_CLIENT_ID
    cf_access_client_secret = settings.WORKER_CF_ACCESS_CLIENT_SECRET
    if cf_access_client_id and cf_access_client_secret:
        headers["CF-Access-Client-Id"] = cf_access_client_id
        headers["CF-Access-Client-Secret"] = cf_access_client_secret

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.WORKER_CALLBACK_TIMEOUT_SEC)
        ) as client:
            response = await client.post(callback_url, json=payload.model_dump(), headers=headers)
            response.raise_for_status()
    except Exception:
        logger.exception("Failed to callback HollowForge for worker job %s", row["id"])


async def _update_worker_job(worker_job_id: str, **fields: Any) -> dict[str, Any]:
    now = now_iso()
    assignments = []
    params: list[Any] = []
    for key, value in fields.items():
        assignments.append(f"{key} = ?")
        params.append(value)
    assignments.append("updated_at = ?")
    params.append(now)
    params.append(worker_job_id)

    async with get_db() as db:
        await db.execute(
            f"UPDATE worker_jobs SET {', '.join(assignments)} WHERE id = ?",
            params,
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM worker_jobs WHERE id = ?",
            (worker_job_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        raise RuntimeError(f"Worker job {worker_job_id} disappeared after update")
    return row


async def _cleanup_stale_worker_jobs() -> int:
    now = now_iso()
    stale_statuses = ("queued", "submitted", "processing")

    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT *
            FROM worker_jobs
            WHERE status IN ({", ".join("?" for _ in stale_statuses)})
            ORDER BY updated_at ASC
            """,
            stale_statuses,
        )
        rows = await cursor.fetchall()
        for row in rows:
            await db.execute(
                """
                UPDATE worker_jobs
                SET status = ?, error_message = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                ("failed", "Worker restarted", now, now, row["id"]),
            )
        await db.commit()

    callback_tasks = []
    for row in rows:
        if row.get("callback_url"):
            callback_row = dict(row)
            callback_row["status"] = "failed"
            callback_row["error_message"] = "Worker restarted"
            callback_row["completed_at"] = now
            callback_row["updated_at"] = now
            callback_tasks.append(
                _notify_hollowforge(
                    callback_row,
                    HollowForgeCallbackPayload(
                        status="failed",
                        external_job_id=callback_row.get("external_job_id"),
                        external_job_url=callback_row.get("external_job_url"),
                        error_message="Worker restarted",
                    ),
                )
            )

    if callback_tasks:
        await asyncio.gather(*callback_tasks, return_exceptions=True)

    return len(rows)


async def _run_worker_job(worker_job_id: str) -> None:
    executor = build_executor(
        outputs_dir=settings.OUTPUTS_DIR,
        public_base_url=settings.WORKER_PUBLIC_BASE_URL,
    )

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM worker_jobs WHERE id = ?",
            (worker_job_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return

    try:
        submitted = await executor.submit(row)
        row = await _update_worker_job(
            worker_job_id,
            status="submitted",
            external_job_id=submitted.external_job_id,
            external_job_url=submitted.external_job_url,
            submitted_at=now_iso(),
        )
        await _notify_hollowforge(
            row,
            HollowForgeCallbackPayload(
                status="submitted",
                external_job_id=row.get("external_job_id"),
                external_job_url=row.get("external_job_url"),
            ),
        )

        row = await _update_worker_job(worker_job_id, status="processing")
        await _notify_hollowforge(
            row,
            HollowForgeCallbackPayload(
                status="processing",
                external_job_id=row.get("external_job_id"),
                external_job_url=row.get("external_job_url"),
            ),
        )

        completed = await executor.wait_for_completion(worker_job_id)
        row = await _update_worker_job(
            worker_job_id,
            status="completed",
            output_url=completed.output_url,
            error_message=completed.error_message,
            completed_at=now_iso(),
        )
        await _notify_hollowforge(
            row,
            HollowForgeCallbackPayload(
                status="completed",
                external_job_id=row.get("external_job_id"),
                external_job_url=row.get("external_job_url"),
                output_path=_callback_output_path(row.get("output_url")),
                output_url=row.get("output_url"),
                error_message=row.get("error_message"),
            ),
        )
    except Exception as exc:
        logger.exception("Worker job %s failed", worker_job_id)
        row = await _update_worker_job(
            worker_job_id,
            status="failed",
            error_message=str(exc),
            completed_at=now_iso(),
        )
        await _notify_hollowforge(
            row,
            HollowForgeCallbackPayload(
                status="failed",
                external_job_id=row.get("external_job_id"),
                external_job_url=row.get("external_job_url"),
                error_message=row.get("error_message"),
            ),
        )


def _schedule_job(app: FastAPI, worker_job_id: str) -> None:
    if not hasattr(app.state, "worker_tasks"):
        app.state.worker_tasks = set()
    task = asyncio.create_task(_run_worker_job(worker_job_id))
    app.state.worker_tasks.add(task)
    task.add_done_callback(app.state.worker_tasks.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _cleanup_stale_worker_jobs()
    settings.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    settings.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    app.state.worker_tasks = set()
    yield


app = FastAPI(
    title="Lab451 Execution Worker",
    version="0.1.0",
    description="Separate execution worker for HollowForge animation and comic still jobs",
    lifespan=lifespan,
)

app.mount(
    "/data/outputs",
    StaticFiles(directory=str(settings.OUTPUTS_DIR)),
    name="worker-outputs",
)


@app.get("/healthz", response_model=WorkerHealthResponse)
async def healthz() -> WorkerHealthResponse:
    return WorkerHealthResponse(
        status="ok",
        executor_backend=settings.WORKER_EXECUTOR_BACKEND,
    )


@app.get("/api/v1/jobs", response_model=list[WorkerJobResponse])
async def list_jobs(
    authorization: str | None = Header(default=None),
) -> list[WorkerJobResponse]:
    _require_api_token(authorization)
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM worker_jobs ORDER BY updated_at DESC LIMIT 200"
        )
        rows = await cursor.fetchall()
    return [_row_to_response(row) for row in rows]


@app.get("/api/v1/jobs/{worker_job_id}", response_model=WorkerJobResponse)
async def get_job(
    worker_job_id: str,
    authorization: str | None = Header(default=None),
) -> WorkerJobResponse:
    _require_api_token(authorization)
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM worker_jobs WHERE id = ?",
            (worker_job_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker job {worker_job_id} not found",
        )
    return _row_to_response(row)


@app.post("/api/v1/jobs", response_model=WorkerJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: WorkerJobCreate,
    authorization: str | None = Header(default=None),
) -> WorkerJobResponse:
    _require_api_token(authorization)
    worker_job_id = str(uuid4())
    now = now_iso()

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO worker_jobs (
                id,
                hollowforge_job_id,
                candidate_id,
                generation_id,
                publish_job_id,
                target_tool,
                executor_mode,
                executor_key,
                status,
                source_image_url,
                generation_metadata,
                request_json,
                callback_url,
                callback_token,
                external_job_id,
                external_job_url,
                output_url,
                error_message,
                submitted_at,
                completed_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                worker_job_id,
                payload.hollowforge_job_id,
                payload.candidate_id,
                payload.generation_id,
                payload.publish_job_id,
                payload.target_tool,
                payload.executor_mode,
                payload.executor_key,
                str(payload.source_image_url) if payload.source_image_url else "",
                json.dumps(payload.generation_metadata, ensure_ascii=False)
                if payload.generation_metadata is not None
                else None,
                json.dumps(payload.request_json, ensure_ascii=False)
                if payload.request_json is not None
                else None,
                str(payload.callback_url) if payload.callback_url else None,
                payload.callback_token,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM worker_jobs WHERE id = ?",
            (worker_job_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create worker job",
        )

    _schedule_job(app, worker_job_id)
    return _row_to_response(row)


@app.post("/api/v1/jobs/{worker_job_id}/retry", response_model=WorkerJobResponse)
async def retry_job(
    worker_job_id: str,
    authorization: str | None = Header(default=None),
) -> WorkerJobResponse:
    _require_api_token(authorization)
    row = await _update_worker_job(
        worker_job_id,
        status="queued",
        error_message=None,
        completed_at=None,
    )
    _schedule_job(app, worker_job_id)
    return _row_to_response(row)
