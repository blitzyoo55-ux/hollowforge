from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI
import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.routes import animation as animation_routes
from app.services import animation_reconciliation_service


def _now() -> str:
    return "2026-04-05T12:00:00+00:00"


def _load_script_module(filename: str, module_name: str):
    module_path = Path(__file__).resolve().parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _insert_animation_job(
    temp_db: Path,
    *,
    job_id: str,
    status: str,
    external_job_id: str | None,
    external_job_url: str | None = None,
    output_path: str | None = None,
    error_message: str | None = "stale error",
    executor_mode: str = "remote_worker",
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
                executor_mode,
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


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(animation_routes.router)
    return app


class _FakeComfyUIClient:
    async def close(self) -> None:
        return None


class _FakeGenerationService:
    def __init__(self, *_args, **_kwargs) -> None:
        self.cleanup_calls = 0

    async def cleanup_stale(self) -> int:
        self.cleanup_calls += 1
        return 0

    def start_worker(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None


class _FakeFavoriteUpscaleService:
    def __init__(self, *_args, **_kwargs) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        return None


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
async def test_backend_startup_invokes_animation_reconciliation(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as backend_main

    calls: list[str] = []

    async def _fake_init_db() -> None:
        calls.append("init_db")

    async def _fake_reconcile() -> dict[str, int]:
        calls.append("reconcile")
        return {
            "checked": 1,
            "updated": 1,
            "failed_restart": 0,
            "completed": 1,
            "cancelled": 0,
            "skipped_unreachable": 0,
        }

    monkeypatch.setattr(backend_main, "init_db", _fake_init_db)
    monkeypatch.setattr(backend_main, "reconcile_stale_animation_jobs", _fake_reconcile)
    monkeypatch.setattr(backend_main, "ComfyUIClient", _FakeComfyUIClient)
    monkeypatch.setattr(backend_main, "GenerationService", _FakeGenerationService)
    monkeypatch.setattr(backend_main, "FavoriteUpscaleService", _FakeFavoriteUpscaleService)

    app = FastAPI()
    app.state.routers_initialized = True

    async with backend_main.lifespan(app):
        calls.append("booted")

    assert calls == ["init_db", "reconcile", "booted"]


def test_reconcile_stale_animation_jobs_script_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    temp_db: Path,
) -> None:
    module = _load_script_module(
        "reconcile_stale_animation_jobs.py",
        "reconcile_stale_animation_jobs",
    )

    _insert_animation_job(
        temp_db,
        job_id="anim-job-completed",
        status="processing",
        external_job_id="worker-job-completed",
        external_job_url="https://worker.test/jobs/worker-job-completed",
    )
    _insert_animation_job(
        temp_db,
        job_id="anim-job-missing",
        status="submitted",
        external_job_id="worker-job-missing",
        external_job_url="https://worker.test/jobs/worker-job-missing",
    )
    _insert_animation_job(
        temp_db,
        job_id="anim-job-local",
        status="queued",
        external_job_id="worker-job-local",
        external_job_url="https://worker.test/jobs/worker-job-local",
        executor_mode="local",
    )

    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(settings, "ANIMATION_WORKER_API_TOKEN", "worker-token")
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "callback-token")

    backend_app = _build_app()
    real_async_client = httpx.AsyncClient
    worker_responses = {
        "worker-job-completed": httpx.Response(
            200,
            request=httpx.Request("GET", "http://worker.test/api/v1/jobs/worker-job-completed"),
            json={
                "status": "completed",
                "output_url": "https://worker.test/data/outputs/reconciled.mp4",
            },
        ),
        "worker-job-missing": httpx.Response(
            404,
            request=httpx.Request("GET", "http://worker.test/api/v1/jobs/worker-job-missing"),
            json={"detail": "not found"},
        ),
    }
    created_clients: list[object] = []

    class _FakeHttpClient:
        def __init__(self, *args, **kwargs) -> None:
            self.base_url = str(kwargs.get("base_url") or "")
            self.requests: list[tuple[str, str, dict[str, str], object | None]] = []
            self._backend_client: object | None = None
            created_clients.append(self)

        async def __aenter__(self) -> "_FakeHttpClient":
            if self.base_url == "http://127.0.0.1:8000":
                self._backend_client = real_async_client(
                    transport=ASGITransport(app=backend_app),
                    base_url=self.base_url,
                )
                await self._backend_client.__aenter__()
                return self
            if self.base_url == "http://worker.test":
                return self
            raise AssertionError(f"Unexpected base_url: {self.base_url}")

        async def __aexit__(self, exc_type, exc, tb) -> None:
            if self._backend_client is not None:
                await self._backend_client.__aexit__(exc_type, exc, tb)

        async def get(self, url: str, *, headers=None, params=None):  # type: ignore[no-untyped-def]
            self.requests.append(("GET", self.base_url, dict(headers or {}), params))
            if self.base_url == "http://127.0.0.1:8000":
                assert self._backend_client is not None
                return await self._backend_client.get(url, headers=headers, params=params)
            if self.base_url == "http://worker.test":
                if "Bearer worker-token" not in dict(headers or {}).get("Authorization", ""):
                    raise AssertionError("worker auth header missing")
                job_id = url.rsplit("/", 1)[-1]
                return worker_responses[job_id]
            raise AssertionError(f"Unexpected GET client base_url: {self.base_url}")

        async def post(self, url: str, *, headers=None, json=None):  # type: ignore[no-untyped-def]
            self.requests.append(("POST", self.base_url, dict(headers or {}), json))
            if self.base_url == "http://127.0.0.1:8000":
                assert self._backend_client is not None
                return await self._backend_client.post(url, headers=headers, json=json)
            raise AssertionError(f"Unexpected POST client base_url: {self.base_url}")

    monkeypatch.setattr(module.httpx, "AsyncClient", _FakeHttpClient)
    monkeypatch.setattr(
        animation_reconciliation_service,
        "reconcile_stale_animation_jobs",
        lambda: (_ for _ in ()).throw(AssertionError("direct service import should not be used")),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["reconcile_stale_animation_jobs.py", "--base-url", "http://127.0.0.1:8000"],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    backend_client = next(client for client in created_clients if client.base_url == "http://127.0.0.1:8000")
    worker_client = next(client for client in created_clients if client.base_url == "http://worker.test")
    assert backend_client.base_url == "http://127.0.0.1:8000"
    assert worker_client.base_url == "http://worker.test"
    assert "checked: 2" in captured.out
    assert "updated: 2" in captured.out
    assert "failed_restart: 1" in captured.out
    assert "completed: 1" in captured.out
    assert "cancelled: 0" in captured.out
    assert "skipped_unreachable: 0" in captured.out
    assert any(
        request[0] == "GET"
        and "Bearer worker-token" in request[2].get("Authorization", "")
        for request in worker_client.requests
    )
    assert any(
        request[0] == "POST"
        and "Bearer callback-token" in request[2].get("Authorization", "")
        for request in backend_client.requests
    )

    completed_payload = next(
        request[3]
        for request in backend_client.requests
        if request[0] == "POST" and request[3].get("status") == "completed"
    )
    assert completed_payload["error_message"] is None

    completed_row = _fetch_animation_job(temp_db, "anim-job-completed")
    missing_row = _fetch_animation_job(temp_db, "anim-job-missing")
    assert completed_row["status"] == "completed"
    assert completed_row["output_path"] == "outputs/reconciled.mp4"
    assert missing_row["status"] == "failed"
    assert missing_row["error_message"] == "Worker restarted"
    local_row = _fetch_animation_job(temp_db, "anim-job-local")
    assert local_row["status"] == "queued"


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_script_ignores_non_remote_worker_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "reconcile_stale_animation_jobs.py",
        "reconcile_stale_animation_jobs_ignore_local_rows",
    )

    calls: list[str] = []

    async def _fake_fetch_worker_job(_worker_client, job_id: str):  # type: ignore[no-untyped-def]
        calls.append(job_id)
        return None

    async def _fake_post_callback(_backend_client, *, job_id: str, payload: dict[str, object]):  # type: ignore[no-untyped-def]
        return None

    backend_jobs_response = httpx.Response(
        200,
        request=httpx.Request("GET", "http://127.0.0.1:8000/api/v1/animation/jobs"),
        json=[
            {
                "id": "anim-job-local",
                "executor_mode": "local",
                "external_job_id": "worker-job-local",
                "external_job_url": "https://worker.test/jobs/worker-job-local",
                "status": "queued",
            },
            {
                "id": "anim-job-remote",
                "executor_mode": "remote_worker",
                "external_job_id": "worker-job-remote",
                "external_job_url": "https://worker.test/jobs/worker-job-remote",
                "status": "processing",
            },
        ],
    )

    class _DummyClient:
        def __init__(self, *args, **kwargs) -> None:
            self.base_url = str(kwargs.get("base_url") or "")

        async def __aenter__(self) -> "_DummyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            if self.base_url == "http://127.0.0.1:8000":
                return backend_jobs_response
            raise AssertionError("worker get should not be called for local row filtering test")

        async def post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(200, request=httpx.Request("POST", "http://127.0.0.1:8000/api/v1/animation/jobs/anim-job-remote/callback"))

    monkeypatch.setattr(module.httpx, "AsyncClient", _DummyClient)
    monkeypatch.setattr(module, "_fetch_worker_job", _fake_fetch_worker_job)
    monkeypatch.setattr(module, "_post_callback", _fake_post_callback)
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")

    summary = await module._reconcile_via_http("http://127.0.0.1:8000")

    assert calls == ["worker-job-remote"]
    assert summary["checked"] == 1
    assert summary["updated"] == 1
    assert summary["failed_restart"] == 1


@pytest.mark.asyncio
async def test_reconcile_stale_animation_jobs_script_raises_on_fatal_worker_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "reconcile_stale_animation_jobs.py",
        "reconcile_stale_animation_jobs_worker_401",
    )

    async def _fake_load_stale_jobs(_backend_client):  # type: ignore[no-untyped-def]
        return [
            {
                "id": "anim-job-401",
                "executor_mode": "remote_worker",
                "external_job_id": "worker-job-401",
                "external_job_url": "https://worker.test/jobs/worker-job-401",
            }
        ]

    async def _fake_fetch_worker_job(_worker_client, job_id: str):  # type: ignore[no-untyped-def]
        raise module._WorkerJobFatalError("worker returned HTTP 401")

    class _DummyClient:
        def __init__(self, *args, **kwargs) -> None:
            self.base_url = str(kwargs.get("base_url") or "")

        async def __aenter__(self) -> "_DummyClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(module.httpx, "AsyncClient", _DummyClient)
    monkeypatch.setattr(module, "_load_stale_jobs", _fake_load_stale_jobs)
    monkeypatch.setattr(module, "_fetch_worker_job", _fake_fetch_worker_job)
    monkeypatch.setattr(settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")

    with pytest.raises(RuntimeError, match="worker returned HTTP 401"):
        await module._reconcile_via_http("http://127.0.0.1:8000")


def test_reconcile_stale_animation_jobs_script_exits_non_zero_on_fatal_worker_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "reconcile_stale_animation_jobs.py",
        "reconcile_stale_animation_jobs_main_worker_401",
    )

    async def _fake_reconcile_via_http(base_url: str) -> dict[str, int]:
        raise RuntimeError("worker returned HTTP 401")

    monkeypatch.setattr(module, "_reconcile_via_http", _fake_reconcile_via_http)
    monkeypatch.setattr(
        sys,
        "argv",
        ["reconcile_stale_animation_jobs.py", "--base-url", "http://127.0.0.1:8000"],
    )

    assert module.main() == 1


@pytest.mark.asyncio
async def test_backend_startup_reconciliation_failure_does_not_abort_boot(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as backend_main

    calls: list[str] = []

    async def _fake_init_db() -> None:
        calls.append("init_db")

    async def _fake_reconcile() -> dict[str, int]:
        calls.append("reconcile")
        raise httpx.ConnectError(
            "worker unreachable",
            request=httpx.Request("GET", "http://worker.test/api/v1/jobs/job-1"),
        )

    monkeypatch.setattr(backend_main, "init_db", _fake_init_db)
    monkeypatch.setattr(backend_main, "reconcile_stale_animation_jobs", _fake_reconcile)
    monkeypatch.setattr(backend_main, "ComfyUIClient", _FakeComfyUIClient)
    monkeypatch.setattr(backend_main, "GenerationService", _FakeGenerationService)
    monkeypatch.setattr(backend_main, "FavoriteUpscaleService", _FakeFavoriteUpscaleService)

    app = FastAPI()
    app.state.routers_initialized = True

    async with backend_main.lifespan(app):
        calls.append("booted")

    assert calls == ["init_db", "reconcile", "booted"]


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


async def _post_animation_callback(
    job_id: str,
    payload: dict[str, object],
    *,
    token: str,
) -> httpx.Response:
    app = _build_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.post(
            f"/api/v1/animation/jobs/{job_id}/callback",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )


@pytest.mark.asyncio
async def test_animation_callback_failed_job_ignores_late_processing(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "anim-job-terminal-failed"
    _insert_animation_job(
        temp_db,
        job_id=job_id,
        status="processing",
        external_job_id="worker-job-failed",
        external_job_url="https://worker.test/jobs/worker-job-failed",
        error_message="initial failure",
    )
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "animation-secret")

    failed = await _post_animation_callback(
        job_id,
        {
            "status": "failed",
            "external_job_id": "worker-job-failed",
            "external_job_url": "https://worker.test/jobs/worker-job-failed",
            "error_message": "initial failure",
            "request_json": {"worker": {"attempt": 1}},
        },
        token="animation-secret",
    )
    assert failed.status_code == 200

    late_processing = await _post_animation_callback(
        job_id,
        {
            "status": "processing",
            "external_job_id": "worker-job-late",
            "external_job_url": "https://worker.test/jobs/worker-job-late",
            "error_message": "late processing",
            "request_json": {"worker": {"attempt": 99}},
        },
        token="animation-secret",
    )

    assert late_processing.status_code == 200
    body = late_processing.json()
    assert body["status"] == "failed"
    assert body["external_job_id"] == "worker-job-failed"
    assert body["external_job_url"] == "https://worker.test/jobs/worker-job-failed"
    assert body["error_message"] == "initial failure"
    assert body["request_json"] == {"worker": {"attempt": 1}}

    row = _fetch_animation_job(temp_db, job_id)
    assert row["status"] == "failed"
    assert row["external_job_id"] == "worker-job-failed"
    assert row["external_job_url"] == "https://worker.test/jobs/worker-job-failed"
    assert row["error_message"] == "initial failure"
    assert row["request_json"] == '{"worker": {"attempt": 1}}'


@pytest.mark.asyncio
async def test_animation_callback_completed_job_ignores_late_failed(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "anim-job-terminal-completed"
    _insert_animation_job(
        temp_db,
        job_id=job_id,
        status="processing",
        external_job_id="worker-job-completed",
        external_job_url="https://worker.test/jobs/worker-job-completed",
        output_path="outputs/final.mp4",
        error_message=None,
    )
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "animation-secret")

    completed = await _post_animation_callback(
        job_id,
        {
            "status": "completed",
            "external_job_id": "worker-job-completed",
            "external_job_url": "https://worker.test/jobs/worker-job-completed",
            "output_path": "outputs/final.mp4",
            "request_json": {"worker": {"attempt": 1}},
        },
        token="animation-secret",
    )
    assert completed.status_code == 200

    late_failed = await _post_animation_callback(
        job_id,
        {
            "status": "failed",
            "external_job_id": "worker-job-late",
            "external_job_url": "https://worker.test/jobs/worker-job-late",
            "error_message": "late failure",
            "request_json": {"worker": {"attempt": 99}},
        },
        token="animation-secret",
    )

    assert late_failed.status_code == 200
    body = late_failed.json()
    assert body["status"] == "completed"
    assert body["external_job_id"] == "worker-job-completed"
    assert body["external_job_url"] == "https://worker.test/jobs/worker-job-completed"
    assert body["output_path"] == "outputs/final.mp4"
    assert body["error_message"] is None
    assert body["request_json"] == {"worker": {"attempt": 1}}

    row = _fetch_animation_job(temp_db, job_id)
    assert row["status"] == "completed"
    assert row["external_job_id"] == "worker-job-completed"
    assert row["external_job_url"] == "https://worker.test/jobs/worker-job-completed"
    assert row["output_path"] == "outputs/final.mp4"
    assert row["error_message"] is None
    assert row["request_json"] == '{"worker": {"attempt": 1}}'


@pytest.mark.asyncio
async def test_animation_callback_completed_job_ignores_duplicate_completed(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "anim-job-terminal-duplicate-completed"
    _insert_animation_job(
        temp_db,
        job_id=job_id,
        status="processing",
        external_job_id="worker-job-completed",
        external_job_url="https://worker.test/jobs/worker-job-completed",
        output_path="outputs/final.mp4",
        error_message=None,
    )
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "animation-secret")

    completed = await _post_animation_callback(
        job_id,
        {
            "status": "completed",
            "external_job_id": "worker-job-completed",
            "external_job_url": "https://worker.test/jobs/worker-job-completed",
            "output_path": "outputs/final.mp4",
            "request_json": {"worker": {"attempt": 1}},
        },
        token="animation-secret",
    )
    assert completed.status_code == 200

    def _stale_snapshot_guard(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("callback should reload the row inside the transaction")

    monkeypatch.setattr(animation_routes, "_require_animation_job", _stale_snapshot_guard)

    duplicate_completed = await _post_animation_callback(
        job_id,
        {
            "status": "completed",
            "external_job_id": "worker-job-duplicate",
            "external_job_url": "https://worker.test/jobs/worker-job-duplicate",
            "output_path": "outputs/duplicate.mp4",
            "error_message": "duplicate should be ignored",
            "request_json": {"worker": {"attempt": 99}},
        },
        token="animation-secret",
    )

    assert duplicate_completed.status_code == 200
    body = duplicate_completed.json()
    assert body["status"] == "completed"
    assert body["external_job_id"] == "worker-job-completed"
    assert body["external_job_url"] == "https://worker.test/jobs/worker-job-completed"
    assert body["output_path"] == "outputs/final.mp4"
    assert body["error_message"] is None
    assert body["request_json"] == {"worker": {"attempt": 1}}

    row = _fetch_animation_job(temp_db, job_id)
    assert row["status"] == "completed"
    assert row["external_job_id"] == "worker-job-completed"
    assert row["external_job_url"] == "https://worker.test/jobs/worker-job-completed"
    assert row["output_path"] == "outputs/final.mp4"
    assert row["error_message"] is None
    assert row["request_json"] == '{"worker": {"attempt": 1}}'


@pytest.mark.asyncio
async def test_animation_callback_cancelled_job_ignores_late_completed(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id = "anim-job-terminal-cancelled"
    _insert_animation_job(
        temp_db,
        job_id=job_id,
        status="queued",
        external_job_id="worker-job-cancelled",
        external_job_url="https://worker.test/jobs/worker-job-cancelled",
        error_message="cancelled by operator",
    )
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "animation-secret")

    cancelled = await _post_animation_callback(
        job_id,
        {
            "status": "cancelled",
            "external_job_id": "worker-job-cancelled",
            "external_job_url": "https://worker.test/jobs/worker-job-cancelled",
            "error_message": "cancelled by operator",
            "request_json": {"worker": {"attempt": 1}},
        },
        token="animation-secret",
    )
    assert cancelled.status_code == 200

    late_completed = await _post_animation_callback(
        job_id,
        {
            "status": "completed",
            "external_job_id": "worker-job-late",
            "external_job_url": "https://worker.test/jobs/worker-job-late",
            "output_path": "outputs/late.mp4",
            "request_json": {"worker": {"attempt": 99}},
        },
        token="animation-secret",
    )

    assert late_completed.status_code == 200
    body = late_completed.json()
    assert body["status"] == "cancelled"
    assert body["external_job_id"] == "worker-job-cancelled"
    assert body["external_job_url"] == "https://worker.test/jobs/worker-job-cancelled"
    assert body["error_message"] == "cancelled by operator"
    assert body["request_json"] == {"worker": {"attempt": 1}}

    row = _fetch_animation_job(temp_db, job_id)
    assert row["status"] == "cancelled"
    assert row["external_job_id"] == "worker-job-cancelled"
    assert row["external_job_url"] == "https://worker.test/jobs/worker-job-cancelled"
    assert row["error_message"] == "cancelled by operator"
    assert row["request_json"] == '{"worker": {"attempt": 1}}'
