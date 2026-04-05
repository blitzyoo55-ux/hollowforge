from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest

from app.config import settings
from app.services import animation_reconciliation_service


def _now() -> str:
    return "2026-04-05T12:00:00+00:00"


def _insert_animation_job(
    temp_db: Path,
    *,
    job_id: str,
    status: str,
    external_job_id: str | None,
    external_job_url: str | None = None,
    output_path: str | None = None,
    error_message: str | None = "stale error",
) -> None:
    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                None,
                "gen-ready-1",
                None,
                "dreamactor",
                "remote_worker",
                "default",
                status,
                None,
                external_job_id,
                external_job_url,
                output_path,
                error_message,
                _now(),
                None,
                _now(),
                _now(),
            ),
        )
        conn.commit()


def _fetch_animation_job(temp_db: Path, job_id: str) -> dict[str, object]:
    with sqlite3.connect(temp_db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM animation_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    assert row is not None
    return dict(row)


class _FakeWorkerClient:
    def __init__(self, responses: dict[str, object]) -> None:
        self._responses = responses
        self.requests: list[tuple[str, dict[str, str]]] = []

    async def __aenter__(self) -> "_FakeWorkerClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, headers: dict[str, str] | None = None) -> httpx.Response:
        self.requests.append((url, dict(headers or {})))
        job_id = url.rsplit("/", 1)[-1]
        response = self._responses[job_id]
        if isinstance(response, Exception):
            raise response
        assert isinstance(response, httpx.Response)
        return response


def _response_for(job_id: str, status_code: int, payload: dict[str, object]) -> httpx.Response:
    request = httpx.Request("GET", f"http://worker.test/api/v1/jobs/{job_id}")
    return httpx.Response(status_code, request=request, json=payload)


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    responses: dict[str, object],
) -> _FakeWorkerClient:
    client = _FakeWorkerClient(responses)
    monkeypatch.setattr(
        animation_reconciliation_service.httpx,
        "AsyncClient",
        lambda *args, **kwargs: client,
    )
    return client


def _install_clip_ready_failure(
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
) -> None:
    async def _raise(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise exc

    monkeypatch.setattr(
        animation_reconciliation_service,
        "mark_shot_clip_ready_for_completed_job",
        _raise,
    )


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_marks_failed_worker_rows_failed(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_animation_job(
        temp_db,
        job_id="anim-job-failed",
        status="processing",
        external_job_id="worker-job-failed",
        external_job_url="https://worker.test/jobs/worker-job-failed",
    )
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(settings, "ANIMATION_WORKER_API_TOKEN", "worker-token")
    client = _install_fake_client(
        monkeypatch,
        {
            "worker-job-failed": _response_for(
                "worker-job-failed",
                200,
                {"status": "failed", "error_message": "worker crashed"},
            )
        },
    )

    result = await animation_reconciliation_service.reconcile_stale_animation_jobs()

    assert result == {
        "checked": 1,
        "updated": 1,
        "failed_restart": 0,
        "completed": 0,
        "cancelled": 0,
        "skipped_unreachable": 0,
    }
    assert client.requests[0][1]["Authorization"] == "Bearer worker-token"

    row = _fetch_animation_job(temp_db, "anim-job-failed")
    assert row["status"] == "failed"
    assert row["error_message"] == "worker crashed"


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_mirrors_completed_worker_output_path(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_animation_job(
        temp_db,
        job_id="anim-job-completed",
        status="submitted",
        external_job_id="worker-job-completed",
        external_job_url="https://worker.test/jobs/worker-job-completed",
        error_message="stale error",
    )
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(settings, "ANIMATION_WORKER_API_TOKEN", "")
    _install_fake_client(
        monkeypatch,
        {
            "worker-job-completed": _response_for(
                "worker-job-completed",
                200,
                {
                    "status": "completed",
                    "output_url": "https://worker.test/data/outputs/example.mp4",
                },
            )
        },
    )

    result = await animation_reconciliation_service.reconcile_stale_animation_jobs()

    assert result["completed"] == 1
    row = _fetch_animation_job(temp_db, "anim-job-completed")
    assert row["status"] == "completed"
    assert row["output_path"] == "outputs/example.mp4"
    assert row["error_message"] is None


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_keeps_going_after_completed_clip_ready_failure(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_animation_job(
        temp_db,
        job_id="anim-job-completed-fallback",
        status="processing",
        external_job_id="worker-job-completed-fallback",
        error_message="stale error",
    )
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    _install_fake_client(
        monkeypatch,
        {
            "worker-job-completed-fallback": _response_for(
                "worker-job-completed-fallback",
                200,
                {
                    "status": "completed",
                    "output_url": "https://worker.test/data/outputs/example.mp4",
                },
            )
        },
    )
    _install_clip_ready_failure(monkeypatch, RuntimeError("clip propagation failed"))

    result = await animation_reconciliation_service.reconcile_stale_animation_jobs()

    assert result["completed"] == 1
    row = _fetch_animation_job(temp_db, "anim-job-completed-fallback")
    assert row["status"] == "completed"
    assert row["output_path"] == "outputs/example.mp4"
    assert row["error_message"] is None


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_skips_unreachable_worker(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_animation_job(
        temp_db,
        job_id="anim-job-unreachable",
        status="processing",
        external_job_id="worker-job-unreachable",
    )
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    _install_fake_client(
        monkeypatch,
        {
            "worker-job-unreachable": httpx.ConnectError(
                "connection refused",
                request=httpx.Request("GET", "http://worker.test/api/v1/jobs/worker-job-unreachable"),
            )
        },
    )

    result = await animation_reconciliation_service.reconcile_stale_animation_jobs()

    assert result["skipped_unreachable"] == 1
    row = _fetch_animation_job(temp_db, "anim-job-unreachable")
    assert row["status"] == "processing"


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_aborts_after_fatal_worker_polling_error(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_animation_job(
        temp_db,
        job_id="anim-job-fatal-1",
        status="processing",
        external_job_id="worker-job-fatal-1",
    )
    _insert_animation_job(
        temp_db,
        job_id="anim-job-fatal-2",
        status="processing",
        external_job_id="worker-job-fatal-2",
    )
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    client = _install_fake_client(
        monkeypatch,
        {
            "worker-job-fatal-1": _response_for(
                "worker-job-fatal-1",
                401,
                {"detail": "missing token"},
            ),
            "worker-job-fatal-2": _response_for(
                "worker-job-fatal-2",
                200,
                {"status": "completed", "output_url": "https://worker.test/data/outputs/skip.mp4"},
            ),
        },
    )

    with pytest.raises(animation_reconciliation_service._WorkerJobFatalError):
        await animation_reconciliation_service.reconcile_stale_animation_jobs()

    assert [request[0] for request in client.requests] == [
        "http://worker.test/api/v1/jobs/worker-job-fatal-1",
    ]


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_treats_missing_worker_job_as_failed_restart(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_animation_job(
        temp_db,
        job_id="anim-job-missing",
        status="processing",
        external_job_id="worker-job-missing",
        error_message=None,
    )
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    _install_fake_client(
        monkeypatch,
        {
            "worker-job-missing": _response_for(
                "worker-job-missing",
                404,
                {"detail": "not found"},
            )
        },
    )

    result = await animation_reconciliation_service.reconcile_stale_animation_jobs()

    assert result["failed_restart"] == 1
    row = _fetch_animation_job(temp_db, "anim-job-missing")
    assert row["status"] == "failed"
    assert row["error_message"] == "Worker restarted"


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_mirrors_cancelled_worker_rows(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _insert_animation_job(
        temp_db,
        job_id="anim-job-cancelled",
        status="queued",
        external_job_id="worker-job-cancelled",
        error_message="stale error",
    )
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    _install_fake_client(
        monkeypatch,
        {
            "worker-job-cancelled": _response_for(
                "worker-job-cancelled",
                200,
                {"status": "cancelled"},
            )
        },
    )

    result = await animation_reconciliation_service.reconcile_stale_animation_jobs()

    assert result["cancelled"] == 1
    row = _fetch_animation_job(temp_db, "anim-job-cancelled")
    assert row["status"] == "cancelled"
