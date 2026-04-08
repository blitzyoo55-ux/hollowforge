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
from app.config import settings
from app.db import init_db
from app.executors import CompletionResult, SubmissionResult
from app.executors import ComfyUILTXVExecutorAdapter
from app.models import HollowForgeCallbackPayload, WorkerJobCreate
from app.workflows import SDXLStillRequest, build_sdxl_still_workflow


class FakeComfyUIClient:
    def __init__(self) -> None:
        self.submitted_workflows: list[dict[str, object]] = []
        self.wait_calls: list[tuple[str, str]] = []
        self.downloaded_assets: list[dict[str, object]] = []
        self.closed = False

    async def check_health(self) -> bool:
        return True

    async def missing_nodes(self, class_types: list[str] | tuple[str, ...]) -> list[str]:
        self.requested_nodes = tuple(class_types)
        return []

    async def get_models(self) -> list[str]:
        return ["comic-checkpoint.safetensors"]

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
