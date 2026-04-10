from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))
(WORKER_ROOT.parent / "data" / "outputs").mkdir(parents=True, exist_ok=True)

from app import main as worker_main
from app import config as worker_config
from app import executors as worker_executors
from app.config import settings
from app.db import init_db
from app.executors import CompletionResult, SubmissionResult
from app.executors import ComfyUILTXVExecutorAdapter
from app.models import HollowForgeCallbackPayload, WorkerJobCreate
from app.workflows import (
    SDXLStillRequest,
    build_sdxl_ipadapter_still_workflow,
    build_sdxl_still_workflow,
    parse_sdxl_ipadapter_still_payload,
)


class FakeComfyUIClient:
    def __init__(self) -> None:
        self.submitted_workflows: list[dict[str, object]] = []
        self.wait_calls: list[tuple[str, str]] = []
        self.downloaded_assets: list[dict[str, object]] = []
        self.uploaded_images: list[tuple[str, bytes]] = []
        self.closed = False

    async def check_health(self) -> bool:
        return True

    async def missing_nodes(self, class_types: list[str] | tuple[str, ...]) -> list[str]:
        self.requested_nodes = tuple(class_types)
        return []

    async def get_models(self) -> list[str]:
        return ["comic-checkpoint.safetensors"]

    async def get_lora_files(self) -> list[str]:
        return [
            "DetailedEyes_V3.safetensors",
            "Face_Enhancer_Illustrious.safetensors",
        ]

    async def get_text_encoders(self) -> list[str]:
        return ["t5xxl_fp16.safetensors"]

    async def get_ipadapter_models(self) -> list[str]:
        return ["ipAdapterPlusSd15_ipAdapterPlusSdxlVit.safetensors"]

    async def get_clip_vision_models(self) -> list[str]:
        return ["CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"]

    async def submit_prompt(self, workflow: dict[str, object]) -> str:
        self.submitted_workflows.append(workflow)
        return "prompt-123"

    async def wait_for_completion(self, prompt_id: str, save_node_id: str) -> list[dict[str, object]]:
        self.wait_calls.append((prompt_id, save_node_id))
        return [{"filename": "panel.png", "subfolder": "lab451_animation_worker", "type": "output"}]

    async def download_asset(self, asset: dict[str, object]) -> bytes:
        self.downloaded_assets.append(asset)
        return b"fake-png-bytes"

    async def upload_image(self, file_path: Path, filename: str) -> str:
        self.uploaded_images.append((filename, file_path.read_bytes()))
        return filename

    async def close(self) -> None:
        self.closed = True


class FakeWorkerExecutor:
    async def submit(self, row: dict[str, object]) -> SubmissionResult:
        return SubmissionResult(
            external_job_id=f"remote-{row['id']}",
            external_job_url=f"https://worker.test/history/{row['id']}",
        )

    async def wait_for_completion(self, worker_job_id: str) -> CompletionResult:
        return CompletionResult(
            output_url=f"https://worker.test/data/outputs/{worker_job_id}.png",
        )


class FakeHttpxResponse:
    def raise_for_status(self) -> None:
        return None


class FakeDownloadResponse:
    def __init__(
        self,
        *,
        content: bytes = b"fake-image-bytes",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.content = content
        self.headers = headers or {"content-type": "image/png"}

    def raise_for_status(self) -> None:
        return None


class CapturingAsyncClient:
    def __init__(self, calls: list[dict[str, object]], *args, **kwargs) -> None:
        self.calls = calls

    async def __aenter__(self) -> CapturingAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(self, url: str, json: dict[str, object], headers: dict[str, str]):
        self.calls.append({"url": url, "json": json, "headers": dict(headers)})
        return FakeHttpxResponse()


class DownloadCapturingAsyncClient:
    def __init__(
        self,
        calls: list[dict[str, object]],
        response: FakeDownloadResponse,
        *args,
        **kwargs,
    ) -> None:
        self.calls = calls
        self.response = response

    async def __aenter__(self) -> DownloadCapturingAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def get(self, url: str, headers: dict[str, str] | None = None):
        self.calls.append({"url": url, "headers": dict(headers or {})})
        return self.response


def _insert_worker_job(
    conn: sqlite3.Connection,
    *,
    worker_job_id: str,
    status: str,
    callback_url: str | None = None,
    callback_token: str | None = None,
    external_job_id: str | None = None,
    external_job_url: str | None = None,
) -> None:
    now = "2026-04-05T00:00:00+00:00"
    conn.execute(
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            worker_job_id,
            f"hollowforge-{worker_job_id}",
            None,
            f"gen-{worker_job_id}",
            None,
            "comic_panel_still",
            "remote_worker",
            "default",
            status,
            "",
            None,
            None,
            callback_url,
            callback_token,
            external_job_id,
            external_job_url,
            None,
            None,
            None,
            None,
            now,
            now,
        ),
    )


def test_worker_job_create_accepts_comic_panel_still_without_source_image_url() -> None:
    payload = WorkerJobCreate.model_validate(
        {
            "hollowforge_job_id": "comic-job-1",
            "generation_id": "gen-1",
            "target_tool": "comic_panel_still",
            "executor_mode": "remote_worker",
            "executor_key": "default",
            "request_json": {
                "backend_family": "sdxl_still",
                "model_profile": "comic_panel_sdxl_v1",
            },
        }
    )

    assert payload.target_tool == "comic_panel_still"
    assert payload.source_image_url is None


def test_notify_hollowforge_includes_cloudflare_access_headers_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(settings, "WORKER_CF_ACCESS_CLIENT_ID", "cf-access-id", raising=False)
    monkeypatch.setattr(
        settings,
        "WORKER_CF_ACCESS_CLIENT_SECRET",
        "cf-access-secret",
        raising=False,
    )
    monkeypatch.setattr(
        worker_main.httpx,
        "AsyncClient",
        lambda *args, **kwargs: CapturingAsyncClient(calls, *args, **kwargs),
    )

    asyncio.run(
        worker_main._notify_hollowforge(
            {
                "id": "worker-job-1",
                "callback_url": "https://hollowforge.test/api/v1/comic/render-jobs/job-1/callback",
                "callback_token": "callback-secret",
            },
            HollowForgeCallbackPayload(
                status="completed",
                output_path="outputs/worker-job-1.png",
            ),
        )
    )

    assert len(calls) == 1
    assert calls[0]["headers"] == {
        "Authorization": "Bearer callback-secret",
        "CF-Access-Client-Id": "cf-access-id",
        "CF-Access-Client-Secret": "cf-access-secret",
    }


def test_notify_hollowforge_skips_partial_cloudflare_access_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(settings, "WORKER_CF_ACCESS_CLIENT_ID", "cf-access-id", raising=False)
    monkeypatch.setattr(settings, "WORKER_CF_ACCESS_CLIENT_SECRET", "", raising=False)
    monkeypatch.setattr(
        worker_main.httpx,
        "AsyncClient",
        lambda *args, **kwargs: CapturingAsyncClient(calls, *args, **kwargs),
    )

    asyncio.run(
        worker_main._notify_hollowforge(
            {
                "id": "worker-job-2",
                "callback_url": "https://hollowforge.test/api/v1/comic/render-jobs/job-2/callback",
                "callback_token": "callback-secret",
            },
            HollowForgeCallbackPayload(
                status="processing",
            ),
        )
    )

    assert len(calls) == 1
    assert calls[0]["headers"] == {
        "Authorization": "Bearer callback-secret",
    }


def test_cleanup_stale_worker_jobs_marks_non_terminal_rows_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "worker-data"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "animation_worker.db")
    monkeypatch.setattr(settings, "INPUTS_DIR", data_dir / "inputs")
    monkeypatch.setattr(settings, "OUTPUTS_DIR", data_dir / "outputs")
    asyncio.run(init_db())

    with sqlite3.connect(settings.DB_PATH) as conn:
        _insert_worker_job(conn, worker_job_id="worker-job-queued", status="queued")
        _insert_worker_job(conn, worker_job_id="worker-job-submitted", status="submitted")
        _insert_worker_job(conn, worker_job_id="worker-job-processing", status="processing")
        conn.commit()

    count = asyncio.run(worker_main._cleanup_stale_worker_jobs())
    assert count == 3

    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = {
            row["id"]: row
            for row in conn.execute(
                """
                SELECT id, status, error_message, completed_at, updated_at
                FROM worker_jobs
                ORDER BY id
                """
            ).fetchall()
        }

    for worker_job_id in (
        "worker-job-queued",
        "worker-job-submitted",
        "worker-job-processing",
    ):
        row = rows[worker_job_id]
        assert row["status"] == "failed"
        assert row["error_message"] == "Worker restarted"
        assert row["completed_at"] is not None
        assert row["updated_at"] == row["completed_at"]


def test_cleanup_stale_worker_jobs_sends_failed_callback_for_rows_with_callback_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "worker-data"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "animation_worker.db")
    monkeypatch.setattr(settings, "INPUTS_DIR", data_dir / "inputs")
    monkeypatch.setattr(settings, "OUTPUTS_DIR", data_dir / "outputs")
    asyncio.run(init_db())

    with sqlite3.connect(settings.DB_PATH) as conn:
        _insert_worker_job(
            conn,
            worker_job_id="worker-job-1",
            status="processing",
            callback_url="https://hollowforge.test/api/v1/jobs/worker-job-1/callback",
            callback_token="callback-secret",
            external_job_id="remote-1",
            external_job_url="https://worker.test/history/remote-1",
        )
        _insert_worker_job(
            conn,
            worker_job_id="worker-job-2",
            status="queued",
        )
        conn.commit()

    payloads: list[tuple[dict[str, object], HollowForgeCallbackPayload]] = []

    async def _fake_notify(row, payload):  # type: ignore[no-untyped-def]
        payloads.append((dict(row), payload))

    monkeypatch.setattr(worker_main, "_notify_hollowforge", _fake_notify)

    count = asyncio.run(worker_main._cleanup_stale_worker_jobs())
    assert count == 2

    assert len(payloads) == 1
    row, payload = payloads[0]
    assert row["id"] == "worker-job-1"
    assert payload.status == "failed"
    assert payload.error_message == "Worker restarted"
    assert payload.external_job_id == "remote-1"
    assert payload.external_job_url == "https://worker.test/history/remote-1"
    assert payload.output_path is None


def test_cleanup_stale_worker_jobs_dispatches_failed_callbacks_concurrently(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "worker-data"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "animation_worker.db")
    monkeypatch.setattr(settings, "INPUTS_DIR", data_dir / "inputs")
    monkeypatch.setattr(settings, "OUTPUTS_DIR", data_dir / "outputs")
    asyncio.run(init_db())

    with sqlite3.connect(settings.DB_PATH) as conn:
        _insert_worker_job(
            conn,
            worker_job_id="worker-job-1",
            status="processing",
            callback_url="https://hollowforge.test/api/v1/jobs/worker-job-1/callback",
        )
        _insert_worker_job(
            conn,
            worker_job_id="worker-job-2",
            status="submitted",
            callback_url="https://hollowforge.test/api/v1/jobs/worker-job-2/callback",
        )
        conn.commit()

    started: list[str] = []
    release = asyncio.Event()

    async def _fake_notify(row, payload):  # type: ignore[no-untyped-def]
        started.append(row["id"])
        await release.wait()

    monkeypatch.setattr(worker_main, "_notify_hollowforge", _fake_notify)

    async def _run_cleanup() -> int:
        cleanup_task = asyncio.create_task(worker_main._cleanup_stale_worker_jobs())
        for _ in range(50):
            if len(started) == 2:
                break
            await asyncio.sleep(0.01)
        assert len(started) == 2
        release.set()
        return await cleanup_task

    count = asyncio.run(_run_cleanup())

    assert count == 2
    assert set(started) == {"worker-job-1", "worker-job-2"}


def test_lifespan_calls_cleanup_stale_worker_jobs_after_init_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def _fake_init_db() -> None:
        calls.append("init_db")

    async def _fake_cleanup() -> None:
        calls.append("cleanup")

    monkeypatch.setattr(worker_main, "init_db", _fake_init_db)
    monkeypatch.setattr(worker_main, "_cleanup_stale_worker_jobs", _fake_cleanup)

    async def _run() -> None:
        async with worker_main.lifespan(worker_main.app):
            calls.append("lifespan_active")

    asyncio.run(_run())

    assert calls == ["init_db", "cleanup", "lifespan_active"]


def test_download_source_image_includes_cloudflare_access_headers_for_trusted_hollowforge_host(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []
    response = FakeDownloadResponse()
    adapter = ComfyUILTXVExecutorAdapter(
        inputs_dir=tmp_path / "inputs",
        outputs_dir=tmp_path / "outputs",
        public_base_url="https://worker.test",
        comfyui_url="https://comfy.example",
    )

    monkeypatch.setattr(settings, "WORKER_CF_ACCESS_CLIENT_ID", "cf-access-id", raising=False)
    monkeypatch.setattr(
        settings,
        "WORKER_CF_ACCESS_CLIENT_SECRET",
        "cf-access-secret",
        raising=False,
    )
    monkeypatch.setattr(
        worker_executors.httpx,
        "AsyncClient",
        lambda *args, **kwargs: DownloadCapturingAsyncClient(calls, response, *args, **kwargs),
    )

    local_path = asyncio.run(
        adapter._download_source_image(
            "worker-job-1",
            "https://sec.hlfglll.com/data/outputs/source-image.png",
            callback_url="https://sec.hlfglll.com/api/v1/animation/jobs/worker-job-1/callback",
        )
    )

    assert len(calls) == 1
    assert calls[0] == {
        "url": "https://sec.hlfglll.com/data/outputs/source-image.png",
        "headers": {
            "CF-Access-Client-Id": "cf-access-id",
            "CF-Access-Client-Secret": "cf-access-secret",
        },
    }
    assert local_path == tmp_path / "inputs" / "worker-job-1.png"
    assert local_path.read_bytes() == b"fake-image-bytes"


def test_download_source_image_skips_partial_cloudflare_access_headers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []
    response = FakeDownloadResponse()
    adapter = ComfyUILTXVExecutorAdapter(
        inputs_dir=tmp_path / "inputs",
        outputs_dir=tmp_path / "outputs",
        public_base_url="https://worker.test",
        comfyui_url="https://comfy.example",
    )

    monkeypatch.setattr(settings, "WORKER_CF_ACCESS_CLIENT_ID", "cf-access-id", raising=False)
    monkeypatch.setattr(settings, "WORKER_CF_ACCESS_CLIENT_SECRET", "", raising=False)
    monkeypatch.setattr(
        worker_executors.httpx,
        "AsyncClient",
        lambda *args, **kwargs: DownloadCapturingAsyncClient(calls, response, *args, **kwargs),
    )

    local_path = asyncio.run(
        adapter._download_source_image(
            "worker-job-2",
            "https://sec.hlfglll.com/data/outputs/source-image.png",
            callback_url="https://sec.hlfglll.com/api/v1/animation/jobs/worker-job-2/callback",
        )
    )

    assert len(calls) == 1
    assert calls[0] == {
        "url": "https://sec.hlfglll.com/data/outputs/source-image.png",
        "headers": {},
    }
    assert local_path == tmp_path / "inputs" / "worker-job-2.png"
    assert local_path.read_bytes() == b"fake-image-bytes"


def test_download_source_image_skips_cloudflare_access_headers_for_untrusted_host(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []
    response = FakeDownloadResponse()
    adapter = ComfyUILTXVExecutorAdapter(
        inputs_dir=tmp_path / "inputs",
        outputs_dir=tmp_path / "outputs",
        public_base_url="https://worker.test",
        comfyui_url="https://comfy.example",
    )

    monkeypatch.setattr(settings, "WORKER_CF_ACCESS_CLIENT_ID", "cf-access-id", raising=False)
    monkeypatch.setattr(
        settings,
        "WORKER_CF_ACCESS_CLIENT_SECRET",
        "cf-access-secret",
        raising=False,
    )
    monkeypatch.setattr(
        worker_executors.httpx,
        "AsyncClient",
        lambda *args, **kwargs: DownloadCapturingAsyncClient(calls, response, *args, **kwargs),
    )

    local_path = asyncio.run(
        adapter._download_source_image(
            "worker-job-3",
            "https://cdn.example.com/data/outputs/source-image.png",
            callback_url="https://sec.hlfglll.com/api/v1/animation/jobs/worker-job-3/callback",
        )
    )

    assert len(calls) == 1
    assert calls[0] == {
        "url": "https://cdn.example.com/data/outputs/source-image.png",
        "headers": {},
    }
    assert local_path == tmp_path / "inputs" / "worker-job-3.png"
    assert local_path.read_bytes() == b"fake-image-bytes"


def test_download_source_image_rejects_non_image_success_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []
    response = FakeDownloadResponse(
        content=b"<!DOCTYPE html>",
        headers={"content-type": "text/html; charset=utf-8"},
    )
    adapter = ComfyUILTXVExecutorAdapter(
        inputs_dir=tmp_path / "inputs",
        outputs_dir=tmp_path / "outputs",
        public_base_url="https://worker.test",
        comfyui_url="https://comfy.example",
    )

    monkeypatch.setattr(settings, "WORKER_CF_ACCESS_CLIENT_ID", "cf-access-id", raising=False)
    monkeypatch.setattr(
        settings,
        "WORKER_CF_ACCESS_CLIENT_SECRET",
        "cf-access-secret",
        raising=False,
    )
    monkeypatch.setattr(
        worker_executors.httpx,
        "AsyncClient",
        lambda *args, **kwargs: DownloadCapturingAsyncClient(calls, response, *args, **kwargs),
    )

    with pytest.raises(RuntimeError, match="non-image content-type"):
        asyncio.run(
            adapter._download_source_image(
                "worker-job-4",
                "https://sec.hlfglll.com/data/outputs/source-image.png",
                callback_url="https://sec.hlfglll.com/api/v1/animation/jobs/worker-job-4/callback",
            )
        )

    assert len(calls) == 1
    assert not (tmp_path / "inputs" / "worker-job-4.png").exists()


def test_worker_job_create_requires_request_json_for_comic_panel_still() -> None:
    with pytest.raises(ValidationError):
        WorkerJobCreate.model_validate(
            {
                "hollowforge_job_id": "comic-job-1",
                "generation_id": "gen-1",
                "target_tool": "comic_panel_still",
                "executor_mode": "remote_worker",
                "executor_key": "default",
            }
        )


def test_worker_job_create_requires_sdxl_still_backend_family_for_comic_panel_still() -> None:
    with pytest.raises(ValidationError):
        WorkerJobCreate.model_validate(
            {
                "hollowforge_job_id": "comic-job-1",
                "generation_id": "gen-1",
                "target_tool": "comic_panel_still",
                "executor_mode": "remote_worker",
                "executor_key": "default",
                "request_json": {
                    "backend_family": "ltxv",
                    "model_profile": "comic_panel_sdxl_v1",
                },
            }
        )


def test_worker_job_create_still_requires_source_image_for_animation_jobs() -> None:
    with pytest.raises(ValidationError):
        WorkerJobCreate.model_validate(
            {
                "hollowforge_job_id": "animation-job-1",
                "generation_id": "gen-1",
                "target_tool": "custom",
                "executor_mode": "remote_worker",
                "executor_key": "default",
            }
        )


def test_sdxl_still_request_preserves_explicit_seed_zero() -> None:
    request = SDXLStillRequest.from_payload(
        {
            "prompt": "panel prompt",
            "checkpoint": "comic-checkpoint.safetensors",
            "seed": 0,
        },
        default_prompt="fallback prompt",
        default_checkpoint="fallback-checkpoint.safetensors",
    )

    assert request.seed == 0


def test_build_sdxl_still_workflow_applies_clip_skip_to_clip_path() -> None:
    request = SDXLStillRequest.from_payload(
        {
            "prompt": "panel prompt",
            "checkpoint": "comic-checkpoint.safetensors",
            "clip_skip": 2,
        },
        default_prompt="fallback prompt",
        default_checkpoint="fallback-checkpoint.safetensors",
    )

    workflow, save_node_id = build_sdxl_still_workflow(
        request=request,
        filename_prefix="lab451_animation_worker/worker-job-1",
    )

    clip_skip_nodes = [
        (node_id, node)
        for node_id, node in workflow.items()
        if node["class_type"] == "CLIPSetLastLayer"
    ]
    assert len(clip_skip_nodes) == 1
    clip_skip_node_id, clip_skip_node = clip_skip_nodes[0]
    assert clip_skip_node["inputs"]["stop_at_clip_layer"] == -2

    positive_nodes = [
        node for node in workflow.values() if node["class_type"] == "CLIPTextEncode"
    ]
    assert len(positive_nodes) == 2
    assert positive_nodes[0]["inputs"]["clip"] == [clip_skip_node_id, 0]
    assert positive_nodes[1]["inputs"]["clip"] == [clip_skip_node_id, 0]
    assert workflow[save_node_id]["class_type"] == "SaveImage"


def test_reference_guided_still_payload_parses_nested_still_generation_and_references() -> None:
    request, reference_images = parse_sdxl_ipadapter_still_payload(
        {
            "backend_family": "sdxl_ipadapter_still",
            "reference_images": [
                "camila_v2_establish_anchor_hero.png",
                "camila_v2_establish_anchor_halfbody.png",
            ],
            "ipadapter_weight": 0.92,
            "ipadapter_start_at": 0.1,
            "ipadapter_end_at": 0.9,
            "still_generation": {
                "prompt": "panel prompt",
                "negative_prompt": "bad anatomy",
                "checkpoint": "comic-checkpoint.safetensors",
                "seed": 77,
                "width": 1216,
                "height": 960,
                "steps": 30,
                "cfg": 5.4,
                "sampler": "euler_ancestral",
                "scheduler": "normal",
            },
        },
        default_prompt="fallback prompt",
        default_checkpoint="fallback-checkpoint.safetensors",
    )

    assert reference_images == (
        "camila_v2_establish_anchor_hero.png",
        "camila_v2_establish_anchor_halfbody.png",
    )
    assert request.prompt == "panel prompt"
    assert request.negative_prompt == "bad anatomy"
    assert request.checkpoint_name == "comic-checkpoint.safetensors"
    assert request.seed == 77
    assert request.width == 1216
    assert request.height == 960
    assert request.steps == 30
    assert request.cfg == pytest.approx(5.4)
    assert request.ipadapter_weight == pytest.approx(0.92)
    assert request.ipadapter_start_at == pytest.approx(0.1)
    assert request.ipadapter_end_at == pytest.approx(0.9)

    workflow, save_node_id = build_sdxl_ipadapter_still_workflow(
        uploaded_image_names=reference_images,
        request=request,
        filename_prefix="lab451_animation_worker/worker-job-reference-guided",
    )

    assert workflow[save_node_id]["class_type"] == "SaveImage"
    assert not any(node["class_type"] == "SaveVideo" for node in workflow.values())
    assert sum(1 for node in workflow.values() if node["class_type"] == "LoadImage") == 2
    assert (
        sum(1 for node in workflow.values() if node["class_type"] == "IPAdapterAdvanced")
        == 2
    )


def test_render_video_from_frames_uses_configured_ffmpeg_binary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    adapter = ComfyUILTXVExecutorAdapter(
        inputs_dir=tmp_path / "inputs",
        outputs_dir=tmp_path / "outputs",
        public_base_url="https://worker.test",
        comfyui_url="https://comfy.example",
    )
    frame_paths = []
    for index in range(2):
        frame_path = tmp_path / f"frame_{index:02d}.png"
        frame_path.write_bytes(b"png")
        frame_paths.append(frame_path)

    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return None

    monkeypatch.setattr(settings, "WORKER_FFMPEG_BIN", "/opt/homebrew/bin/ffmpeg", raising=False)
    monkeypatch.setattr(worker_executors.subprocess, "run", fake_run)

    adapter._render_video_from_frames(
        frame_paths=frame_paths,
        fps=7,
        output_path=tmp_path / "outputs" / "worker-job-1.mp4",
    )

    assert captured["cmd"][0] == "/opt/homebrew/bin/ffmpeg"


def test_comfyui_executor_runs_comic_panel_still_branch(tmp_path: Path) -> None:
    adapter = ComfyUILTXVExecutorAdapter(
        inputs_dir=tmp_path / "inputs",
        outputs_dir=tmp_path / "outputs",
        public_base_url="https://worker.test",
        comfyui_url="https://comfy.example",
    )
    fake_client = FakeComfyUIClient()
    adapter._client = fake_client

    row = {
        "id": "worker-job-1",
        "target_tool": "comic_panel_still",
        "source_image_url": "",
        "generation_metadata": json.dumps(
            {
                "prompt": "fallback prompt",
                "checkpoint": "fallback-checkpoint.safetensors",
            }
        ),
        "request_json": json.dumps(
            {
                "backend_family": "sdxl_still",
                "model_profile": "comic_panel_sdxl_v1",
                "still_generation": {
                    "prompt": "panel prompt",
                    "negative_prompt": "bad anatomy",
                    "checkpoint": "comic-checkpoint.safetensors",
                    "loras": [
                        {
                            "filename": "DetailedEyes_V3.safetensors",
                            "strength": 0.45,
                        }
                    ],
                    "width": 832,
                    "height": 1216,
                    "steps": 34,
                    "cfg": 5.5,
                    "seed": 77,
                    "sampler": "euler_ancestral",
                    "scheduler": "normal",
                    "clip_skip": 2,
                },
            }
        ),
    }

    submission = asyncio.run(adapter.submit(row))

    assert submission.external_job_id == "prompt-123"
    assert submission.external_job_url == "https://comfy.example/history/prompt-123"
    assert fake_client.wait_calls == []
    assert len(fake_client.submitted_workflows) == 1
    workflow = fake_client.submitted_workflows[0]
    lora_loader_node_ids = [
        node_id for node_id, node in workflow.items() if node["class_type"] == "LoraLoader"
    ]
    assert len(lora_loader_node_ids) == 1
    save_image_node_ids = [
        node_id
        for node_id, node in workflow.items()
        if node["class_type"] == "SaveImage"
    ]
    assert len(save_image_node_ids) == 1
    save_image_node_id = save_image_node_ids[0]
    save_image_nodes = [
        node
        for node in workflow.values()
        if node["class_type"] == "SaveImage"
    ]
    assert len(save_image_nodes) == 1
    save_image_node = save_image_nodes[0]
    assert save_image_node["class_type"] == "SaveImage"
    assert save_image_node["inputs"]["filename_prefix"] == "lab451_animation_worker/worker-job-1"

    completed = asyncio.run(adapter.wait_for_completion("worker-job-1"))

    assert completed.output_url == "https://worker.test/data/outputs/worker-job-1.png"
    assert fake_client.wait_calls == [("prompt-123", save_image_node_id)]
    assert fake_client.closed is True
    assert (tmp_path / "outputs" / "worker-job-1.png").read_bytes() == b"fake-png-bytes"


def test_reference_guided_comic_panel_still_routes_to_ipadapter_png_workflow(
    tmp_path: Path,
) -> None:
    adapter = ComfyUILTXVExecutorAdapter(
        inputs_dir=tmp_path / "inputs",
        outputs_dir=tmp_path / "outputs",
        public_base_url="https://worker.test",
        comfyui_url="https://comfy.example",
    )
    fake_client = FakeComfyUIClient()
    adapter._client = fake_client

    download_calls: list[tuple[str, str, str | None]] = []

    async def fake_download_source_image(
        worker_job_id: str,
        source_image_url: str,
        *,
        callback_url: str | None = None,
    ) -> Path:
        download_calls.append((worker_job_id, source_image_url, callback_url))
        local_path = tmp_path / "inputs" / f"{worker_job_id}.png"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(f"image:{worker_job_id}".encode("utf-8"))
        return local_path

    adapter._download_source_image = fake_download_source_image  # type: ignore[method-assign]

    row = {
        "id": "worker-job-reference-guided",
        "target_tool": "comic_panel_still",
        "source_image_url": "",
        "callback_url": "https://sec.hlfglll.com/api/v1/comic/render-jobs/comic-job-1/callback",
        "generation_metadata": json.dumps(
            {
                "prompt": "fallback prompt",
                "checkpoint": "fallback-checkpoint.safetensors",
            }
        ),
        "request_json": json.dumps(
            {
                "backend_family": "sdxl_ipadapter_still",
                "model_profile": "comic_panel_sdxl_v1",
                "reference_images": [
                    "camila_v2_establish_anchor_hero.png",
                    "camila_v2_establish_anchor_halfbody.png",
                ],
                "ipadapter_weight": 0.92,
                "ipadapter_start_at": 0.0,
                "ipadapter_end_at": 1.0,
                "still_generation": {
                    "prompt": "panel prompt",
                    "negative_prompt": "bad anatomy",
                    "checkpoint": "comic-checkpoint.safetensors",
                    "width": 1216,
                    "height": 960,
                    "steps": 30,
                    "cfg": 5.4,
                    "seed": 77,
                    "sampler": "euler_ancestral",
                    "scheduler": "normal",
                },
            }
        ),
    }

    submission = asyncio.run(adapter.submit(row))

    assert submission.external_job_id == "prompt-123"
    assert submission.external_job_url == "https://comfy.example/history/prompt-123"
    assert download_calls == [
        (
            "worker-job-reference-guided_reference_00",
            "https://sec.hlfglll.com/data/outputs/camila_v2_establish_anchor_hero.png",
            "https://sec.hlfglll.com/api/v1/comic/render-jobs/comic-job-1/callback",
        ),
        (
            "worker-job-reference-guided_reference_01",
            "https://sec.hlfglll.com/data/outputs/camila_v2_establish_anchor_halfbody.png",
            "https://sec.hlfglll.com/api/v1/comic/render-jobs/comic-job-1/callback",
        ),
    ]
    assert [item[0] for item in fake_client.uploaded_images] == [
        "worker-job-reference-guided_reference_00.png",
        "worker-job-reference-guided_reference_01.png",
    ]
    assert fake_client.requested_nodes == worker_executors.SDXL_IPADAPTER_REQUIRED_NODES
    assert len(fake_client.submitted_workflows) == 1
    workflow = fake_client.submitted_workflows[0]
    assert sum(1 for node in workflow.values() if node["class_type"] == "LoadImage") == 2
    assert sum(1 for node in workflow.values() if node["class_type"] == "SaveImage") == 1
    assert not any(node["class_type"] == "SaveVideo" for node in workflow.values())
    save_image_node_id = next(
        node_id for node_id, node in workflow.items() if node["class_type"] == "SaveImage"
    )

    completed = asyncio.run(adapter.wait_for_completion("worker-job-reference-guided"))

    assert completed.output_url == "https://worker.test/data/outputs/worker-job-reference-guided.png"
    assert fake_client.wait_calls == [("prompt-123", save_image_node_id)]
    assert fake_client.closed is True
    assert (tmp_path / "outputs" / "worker-job-reference-guided.png").read_bytes() == (
        b"fake-png-bytes"
    )


def test_comfyui_executor_rejects_missing_sdxl_still_loras(tmp_path: Path) -> None:
    adapter = ComfyUILTXVExecutorAdapter(
        inputs_dir=tmp_path / "inputs",
        outputs_dir=tmp_path / "outputs",
        public_base_url="https://worker.test",
        comfyui_url="https://comfy.example",
    )
    fake_client = FakeComfyUIClient()
    adapter._client = fake_client

    row = {
        "id": "worker-job-missing-lora",
        "target_tool": "comic_panel_still",
        "source_image_url": "",
        "generation_metadata": json.dumps(
            {
                "prompt": "fallback prompt",
                "checkpoint": "fallback-checkpoint.safetensors",
            }
        ),
        "request_json": json.dumps(
            {
                "backend_family": "sdxl_still",
                "model_profile": "comic_panel_sdxl_v1",
                "still_generation": {
                    "prompt": "panel prompt",
                    "negative_prompt": "bad anatomy",
                    "checkpoint": "comic-checkpoint.safetensors",
                    "loras": [
                        {
                            "filename": "missing-style-lora.safetensors",
                            "strength": 0.55,
                        }
                    ],
                },
            }
        ),
    }

    with pytest.raises(
        RuntimeError,
        match="ComfyUI is missing requested SDXL still LoRAs: missing-style-lora.safetensors",
    ):
        asyncio.run(adapter.submit(row))


def test_worker_config_defaults_to_shared_repo_data_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WORKER_DATA_DIR", raising=False)
    reloaded = importlib.reload(worker_config)
    try:
        assert reloaded.settings.DATA_DIR == WORKER_ROOT.parent / "data"
        assert reloaded.settings.OUTPUTS_DIR == WORKER_ROOT.parent / "data" / "outputs"
        assert reloaded.settings.INPUTS_DIR == WORKER_ROOT.parent / "data" / "inputs"
    finally:
        importlib.reload(worker_config)


def test_worker_completion_callback_uses_data_relative_output_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "worker-data"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "animation_worker.db")
    monkeypatch.setattr(settings, "INPUTS_DIR", data_dir / "inputs")
    monkeypatch.setattr(settings, "OUTPUTS_DIR", data_dir / "outputs")
    asyncio.run(init_db())

    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.execute(
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "worker-job-1",
                "comic-job-1",
                None,
                "gen-1",
                None,
                "comic_panel_still",
                "remote_worker",
                "default",
                "queued",
                "",
                json.dumps({"prompt": "panel prompt"}, ensure_ascii=False),
                json.dumps(
                    {
                        "backend_family": "sdxl_still",
                        "model_profile": "comic_panel_sdxl_v1",
                        "still_generation": {"prompt": "panel prompt"},
                    },
                    ensure_ascii=False,
                ),
                "https://hollowforge.test/api/v1/comic/render-jobs/comic-job-1/callback",
                "secret-token",
                None,
                None,
                None,
                None,
                None,
                None,
                "2026-04-05T00:00:00+00:00",
                "2026-04-05T00:00:00+00:00",
            ),
        )
        conn.commit()

    payloads = []

    async def _fake_notify(_row, payload):  # type: ignore[no-untyped-def]
        payloads.append(payload)

    monkeypatch.setattr(
        worker_main,
        "build_executor",
        lambda outputs_dir, public_base_url: FakeWorkerExecutor(),
    )
    monkeypatch.setattr(worker_main, "_notify_hollowforge", _fake_notify)

    asyncio.run(worker_main._run_worker_job("worker-job-1"))

    assert [payload.status for payload in payloads] == [
        "submitted",
        "processing",
        "completed",
    ]
    assert payloads[-1].output_path == "outputs/worker-job-1.png"
    assert payloads[-1].output_url == "https://worker.test/data/outputs/worker-job-1.png"
