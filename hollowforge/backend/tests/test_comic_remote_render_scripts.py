from __future__ import annotations

import importlib.util
import sys
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest


def _load_script_module(filename: str, module_name: str):
    module_path = Path(__file__).resolve().parents[1] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _character_context():
    return (
        {
            "id": "char_kaede_ren",
            "slug": "kaede-ren",
            "name": "Kaede Ren",
        },
        {
            "id": "charver_kaede_ren_still_v1",
            "character_id": "char_kaede_ren",
            "version_name": "Still v1",
        },
        [{"id": "char_kaede_ren"}],
        [{"id": "charver_kaede_ren_still_v1"}],
    )


def _patch_comic_verification_persistence(
    module,
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: dict | None = None,
    error: Exception | None = None,
):
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_post_json(url: str, payload: dict[str, object]):  # type: ignore[no-untyped-def]
        calls.append((url, payload))
        if error is not None:
            raise error
        return response or {"id": "comic-verification-run-1"}

    monkeypatch.setattr(module, "_post_json", fake_post_json)
    return calls


def test_preflight_run_passes_when_backend_worker_and_callback_contract_are_ready(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight",
    )

    monkeypatch.setattr(module.settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(module.settings, "PUBLIC_API_BASE_URL", "https://hollowforge.example.com")
    monkeypatch.setattr(module.settings, "ANIMATION_WORKER_API_TOKEN", "worker-secret")

    def fake_fetch_json(url: str, headers=None):  # type: ignore[no-untyped-def]
        if url == "http://127.0.0.1:8000/api/v1/system/health":
            return {"status": "healthy", "db_ok": True}
        if url == "https://hollowforge.example.com/api/v1/system/health":
            return {"status": "healthy", "db_ok": True}
        if url == "http://worker.test/healthz":
            return {"status": "ready", "executor_backend": "stub"}
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "_detect_worker_auth_required", lambda base_url: True)
    post_calls = _patch_comic_verification_persistence(module, monkeypatch)

    assert module.run([]) == 0

    output = capsys.readouterr().out
    assert "[PASS] local_backend_health:" in output
    assert "[PASS] remote_worker_health:" in output
    assert "[PASS] callback_base_url:" in output
    assert "[PASS] worker_api_token:" in output
    assert "comic_verification_run_persisted: true" in output
    assert post_calls[0][0] == "http://127.0.0.1:8000/api/v1/production/comic-verification/runs"
    payload = post_calls[0][1]
    assert payload["run_mode"] == "preflight"
    assert payload["status"] == "completed"
    assert payload["overall_success"] is True
    assert payload["failure_stage"] is None
    assert payload["error_summary"] is None
    assert payload["base_url"] == "http://127.0.0.1:8000"
    assert payload["stage_status"]["local_backend_health"]["status"] == "passed"
    assert payload["stage_status"]["worker_api_token"]["status"] == "passed"


def test_preflight_run_fails_when_persistence_post_fails_after_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_persistence_failure",
    )

    monkeypatch.setattr(module.settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(module.settings, "PUBLIC_API_BASE_URL", "https://hollowforge.example.com")
    monkeypatch.setattr(module.settings, "ANIMATION_WORKER_API_TOKEN", "worker-secret")

    def fake_fetch_json(url: str, headers=None):  # type: ignore[no-untyped-def]
        if url == "http://127.0.0.1:8000/api/v1/system/health":
            return {"status": "healthy", "db_ok": True}
        if url == "https://hollowforge.example.com/api/v1/system/health":
            return {"status": "healthy", "db_ok": True}
        if url == "http://worker.test/healthz":
            return {"status": "ready", "executor_backend": "stub"}
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "_detect_worker_auth_required", lambda base_url: True)
    _patch_comic_verification_persistence(
        module,
        monkeypatch,
        error=RuntimeError("backend persistence failed"),
    )

    assert module.run([]) == 1

    output = capsys.readouterr().out
    assert "comic_verification_run_persisted: false" in output
    assert "backend persistence failed" in output


def test_preflight_fails_when_worker_auth_is_enabled_but_token_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_missing_token",
    )

    monkeypatch.setattr(module.settings, "ANIMATION_WORKER_API_TOKEN", "")

    result = module._check_worker_api_token(auth_required=True)

    assert result.status == "FAIL"
    assert "ANIMATION_WORKER_API_TOKEN" in result.detail


def test_detect_worker_auth_required_returns_true_for_401_and_403() -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_auth_required",
    )

    for status_code in (401, 403):
        def fake_urlopen(request, timeout=5, *, _status_code=status_code):  # type: ignore[no-untyped-def]
            raise HTTPError(
                url=request.full_url,
                code=_status_code,
                msg="auth required",
                hdrs=None,
                fp=BytesIO(b""),
            )

        module.urlopen = fake_urlopen
        assert module._detect_worker_auth_required("http://worker.test") is True


def test_detect_worker_auth_required_returns_none_for_404_and_405() -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_auth_unknown",
    )

    for status_code in (404, 405):
        def fake_urlopen(request, timeout=5, *, _status_code=status_code):  # type: ignore[no-untyped-def]
            raise HTTPError(
                url=request.full_url,
                code=_status_code,
                msg="method unsupported",
                hdrs=None,
                fp=BytesIO(b""),
            )

        module.urlopen = fake_urlopen
        assert module._detect_worker_auth_required("http://worker.test") is None


def test_preflight_fails_when_callback_base_url_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_bad_callback_url",
    )

    monkeypatch.setattr(module.settings, "PUBLIC_API_BASE_URL", "not-a-url")

    result = module._check_callback_base_url(worker_base_url="http://worker.test")

    assert result.status == "FAIL"
    assert "PUBLIC_API_BASE_URL" in result.detail


def test_preflight_run_fails_when_backend_health_is_degraded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_degraded_backend",
    )

    monkeypatch.setattr(module.settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(module.settings, "PUBLIC_API_BASE_URL", "https://hollowforge.example.com")
    monkeypatch.setattr(module.settings, "ANIMATION_WORKER_API_TOKEN", "worker-secret")

    def fake_fetch_json(url: str, headers=None):  # type: ignore[no-untyped-def]
        if url == "http://127.0.0.1:8000/api/v1/system/health":
            return {"status": "degraded", "db_ok": False}
        if url == "https://hollowforge.example.com/api/v1/system/health":
            return {"status": "healthy", "db_ok": True}
        if url == "http://worker.test/healthz":
            return {"status": "ready", "executor_backend": "stub"}
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "_detect_worker_auth_required", lambda base_url: True)
    post_calls = _patch_comic_verification_persistence(module, monkeypatch)

    assert module.run([]) == 1

    output = capsys.readouterr().out
    assert "[FAIL] local_backend_health:" in output
    assert "status='degraded'" in output
    assert post_calls[0][1]["status"] == "failed"
    assert post_calls[0][1]["failure_stage"] == "local_backend_health"
    assert post_calls[0][1]["overall_success"] is False


def test_preflight_run_rejects_non_local_backend_urls(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_remote_backend",
    )

    monkeypatch.setattr(module.settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(module.settings, "PUBLIC_API_BASE_URL", "https://hollowforge.example.com")
    monkeypatch.setattr(module.settings, "ANIMATION_WORKER_API_TOKEN", "worker-secret")

    def fake_fetch_json(url: str, headers=None):  # type: ignore[no-untyped-def]
        if url == "https://hollowforge.example.com/api/v1/system/health":
            return {"status": "healthy", "db_ok": True}
        if url == "http://worker.test/healthz":
            return {"status": "ready", "executor_backend": "stub"}
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "_detect_worker_auth_required", lambda base_url: True)
    _patch_comic_verification_persistence(module, monkeypatch)

    assert module.run(["--backend-url", "https://remote.example.com"]) == 1

    output = capsys.readouterr().out
    assert "[FAIL] local_backend_health:" in output
    assert "local backend URLs" in output


def test_preflight_run_skips_worker_token_when_auth_probe_is_inconclusive(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_probe_inconclusive",
    )

    monkeypatch.setattr(module.settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(module.settings, "PUBLIC_API_BASE_URL", "https://hollowforge.example.com")
    monkeypatch.setattr(module.settings, "ANIMATION_WORKER_API_TOKEN", "")

    def fake_fetch_json(url: str, headers=None):  # type: ignore[no-untyped-def]
        if url in {
            "http://127.0.0.1:8000/api/v1/system/health",
            "https://hollowforge.example.com/api/v1/system/health",
        }:
            return {"status": "healthy", "db_ok": True}
        if url == "http://worker.test/healthz":
            return {"status": "ready", "executor_backend": "stub"}
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "_detect_worker_auth_required", lambda base_url: None)
    _patch_comic_verification_persistence(module, monkeypatch)

    assert module.run([]) == 0

    output = capsys.readouterr().out
    assert "[SKIP] worker_api_token: auth probe inconclusive" in output


def test_preflight_run_fails_when_remote_worker_uses_loopback_callback_base(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_remote_worker_loopback_callback",
    )

    monkeypatch.setattr(module.settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(module.settings, "PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(module.settings, "ANIMATION_WORKER_API_TOKEN", "worker-secret")

    def fake_fetch_json(url: str, headers=None):  # type: ignore[no-untyped-def]
        if url == "http://127.0.0.1:8000/api/v1/system/health":
            return {"status": "healthy", "db_ok": True}
        if url == "http://worker.test/healthz":
            return {"status": "ready", "executor_backend": "stub"}
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "_detect_worker_auth_required", lambda base_url: True)
    _patch_comic_verification_persistence(module, monkeypatch)

    assert module.run([]) == 1

    output = capsys.readouterr().out
    assert "[FAIL] callback_base_url:" in output
    assert "worker-reachable" in output


def test_preflight_run_fails_when_callback_base_health_is_degraded(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_callback_health_degraded",
    )

    monkeypatch.setattr(module.settings, "ANIMATION_REMOTE_BASE_URL", "http://worker.test")
    monkeypatch.setattr(module.settings, "PUBLIC_API_BASE_URL", "https://hollowforge.example.com")
    monkeypatch.setattr(module.settings, "ANIMATION_WORKER_API_TOKEN", "worker-secret")

    def fake_fetch_json(url: str, headers=None):  # type: ignore[no-untyped-def]
        if url == "http://127.0.0.1:8000/api/v1/system/health":
            return {"status": "healthy", "db_ok": True}
        if url == "https://hollowforge.example.com/api/v1/system/health":
            return {"status": "degraded", "db_ok": False}
        if url == "http://worker.test/healthz":
            return {"status": "ready", "executor_backend": "stub"}
        raise AssertionError(f"Unexpected url: {url}")

    monkeypatch.setattr(module, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(module, "_detect_worker_auth_required", lambda base_url: True)
    _patch_comic_verification_persistence(module, monkeypatch)

    assert module.run([]) == 1

    output = capsys.readouterr().out
    assert "[FAIL] callback_base_url:" in output
    assert "unhealthy" in output


def test_queue_and_select_remote_panel_asset_polls_until_materialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_script_module(
        "launch_comic_remote_render_smoke.py",
        "launch_comic_remote_render_smoke_polling",
    )
    base_url = "http://127.0.0.1:8000"
    queue_url = (
        f"{base_url}/api/v1/comic/panels/panel-1/queue-renders"
        "?candidate_count=3&execution_mode=remote_worker"
    )
    jobs_url = f"{base_url}/api/v1/comic/panels/panel-1/render-jobs"
    select_url = f"{base_url}/api/v1/comic/panels/panel-1/assets/asset-2/select"
    queue_response = {
        "execution_mode": "remote_worker",
        "requested_count": 3,
        "queued_generation_count": 3,
        "materialized_asset_count": 0,
        "pending_render_job_count": 3,
        "remote_job_count": 3,
        "render_assets": [
            {"id": "asset-1", "storage_path": "", "is_selected": False},
            {"id": "asset-2", "storage_path": "", "is_selected": False},
            {"id": "asset-3", "storage_path": "", "is_selected": False},
        ],
    }
    jobs_responses = [
        [
            {
                "id": "job-1",
                "scene_panel_id": "panel-1",
                "render_asset_id": "asset-1",
                "generation_id": "gen-1",
                "request_index": 0,
                "source_id": "comic-panel-render:panel-1:3:remote_worker",
                "target_tool": "comic_panel_still",
                "executor_mode": "remote_worker",
                "executor_key": "default",
                "status": "processing",
                "request_json": {"comic": {"render_asset_id": "asset-1"}},
                "output_path": None,
                "created_at": "2026-04-04T00:00:00+00:00",
                "updated_at": "2026-04-04T00:00:01+00:00",
            }
        ],
        [
            {
                "id": "job-2",
                "scene_panel_id": "panel-1",
                "render_asset_id": "asset-2",
                "generation_id": "gen-2",
                "request_index": 1,
                "source_id": "comic-panel-render:panel-1:3:remote_worker",
                "target_tool": "comic_panel_still",
                "executor_mode": "remote_worker",
                "executor_key": "default",
                "status": "completed",
                "request_json": {"comic": {"render_asset_id": "asset-2"}},
                "output_path": "images/comics/panel-1-a.png",
                "created_at": "2026-04-04T00:00:00+00:00",
                "updated_at": "2026-04-04T00:00:02+00:00",
            }
        ],
    ]
    calls: list[tuple[str, str]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url))
        if (method, url) == ("POST", queue_url):
            return queue_response
        if (method, url) == ("GET", jobs_url):
            return jobs_responses.pop(0)
        if (method, url) == ("POST", select_url):
            return {
                "id": "asset-2",
                "scene_panel_id": "panel-1",
                "asset_role": "selected",
                "storage_path": "images/comics/panel-1-a.png",
                "is_selected": True,
            }
        raise AssertionError(f"Unexpected request: {(method, url)!r} payload={payload!r}")

    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    queue_response, selected_asset, render_jobs = module._queue_and_select_remote_panel_asset(
        base_url=base_url,
        panel_id="panel-1",
        candidate_count=3,
        poll_attempts=2,
        poll_sec=0.0,
    )

    assert queue_response["execution_mode"] == "remote_worker"
    assert selected_asset["id"] == "asset-2"
    assert selected_asset["storage_path"] == "images/comics/panel-1-a.png"
    assert len(render_jobs) == 1
    assert render_jobs[0]["render_asset_id"] == "asset-2"
    assert calls.count(("POST", queue_url)) == 1
    assert calls.count(("GET", jobs_url)) == 2


def test_main_prints_success_markers_for_remote_render_smoke(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "launch_comic_remote_render_smoke.py",
        "launch_comic_remote_render_smoke",
    )
    base_url = "http://127.0.0.1:8000"
    queue_url = (
        f"{base_url}/api/v1/comic/panels/panel-1/queue-renders"
        "?candidate_count=3&execution_mode=remote_worker"
    )
    jobs_url = f"{base_url}/api/v1/comic/panels/panel-1/render-jobs"
    select_url = f"{base_url}/api/v1/comic/panels/panel-1/assets/asset-2/select"
    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "Remote render smoke prompt",
            "lane": "adult_nsfw",
            "approval_token": "a" * 64,
            "anchor_render": {
                "prompt": "anchor prompt",
                "negative_prompt": "anchor negative",
                "checkpoint": "waiIllustriousSDXL_v160.safetensors",
                "workflow_lane": "sdxl_illustrious",
                "policy_pack_id": "adult_nsfw_default",
            },
            "resolved_cast": [],
            "location": {
                "id": "private-lounge",
                "name": "Private Lounge",
                "setting_anchor": "Quiet private lounge after closing.",
                "visual_rules": [],
                "restricted_elements": [],
                "match_note": "matched",
            },
            "episode_brief": {
                "title": "Night Intake",
                "logline": "Kaede pauses with a sealed invitation.",
                "core_conflict": "Decide whether to open the invitation.",
                "stakes": "Accepting changes the night.",
                "tone": "quiet tension",
            },
            "shots": [
                {
                    "shot_no": 1,
                    "beat": "Hook the moment",
                    "camera": "Medium close-up.",
                    "action": "Kaede studies the invitation.",
                    "emotion": "Measured curiosity",
                    "continuity_note": "Same wardrobe and lighting.",
                }
            ],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-remote-smoke-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
                "title": "Comic Remote Render Smoke",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [{"id": "panel-1", "panel_no": 1}],
                }
            ],
            "pages": [],
        },
        ("POST", select_url): {
            "id": "asset-2",
            "scene_panel_id": "panel-1",
            "asset_role": "selected",
            "storage_path": "images/comics/panel-1-a.png",
            "is_selected": True,
        },
    }
    responses[("POST", queue_url)] = {
        "execution_mode": "remote_worker",
        "requested_count": 3,
        "queued_generation_count": 3,
        "materialized_asset_count": 0,
        "pending_render_job_count": 3,
        "remote_job_count": 3,
        "render_assets": [
            {"id": "asset-1", "storage_path": "", "is_selected": False},
            {"id": "asset-2", "storage_path": "", "is_selected": False},
            {"id": "asset-3", "storage_path": "", "is_selected": False},
        ],
    }
    jobs_responses = [
        [
            {
                "id": "job-1",
                "scene_panel_id": "panel-1",
                "render_asset_id": "asset-1",
                "generation_id": "gen-1",
                "request_index": 0,
                "source_id": "comic-panel-render:panel-1:3:remote_worker",
                "target_tool": "comic_panel_still",
                "executor_mode": "remote_worker",
                "executor_key": "default",
                "status": "processing",
                "request_json": {"comic": {"render_asset_id": "asset-1"}},
                "output_path": None,
                "created_at": "2026-04-04T00:00:00+00:00",
                "updated_at": "2026-04-04T00:00:01+00:00",
            }
        ],
        [
            {
                "id": "job-2",
                "scene_panel_id": "panel-1",
                "render_asset_id": "asset-2",
                "generation_id": "gen-2",
                "request_index": 1,
                "source_id": "comic-panel-render:panel-1:3:remote_worker",
                "target_tool": "comic_panel_still",
                "executor_mode": "remote_worker",
                "executor_key": "default",
                "status": "completed",
                "request_json": {"comic": {"render_asset_id": "asset-2"}},
                "output_path": "images/comics/panel-1-a.png",
                "created_at": "2026-04-04T00:00:00+00:00",
                "updated_at": "2026-04-04T00:00:02+00:00",
            }
        ],
    ]

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url)
        if key == ("GET", jobs_url):
            return jobs_responses.pop(0)
        if key in responses:
            return responses[key]
        raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")

    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: _character_context(),
    )
    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_remote_render_smoke.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 0

    output = capsys.readouterr().out
    assert "import_success: true" in output
    assert "episode_id: comic-remote-smoke-1" in output
    assert "execution_mode: remote_worker" in output
    assert "queue_renders_success: true" in output
    assert "materialized_asset_count: 1" in output
    assert "selected_panel_asset_count: 1" in output
    assert "real_selected_asset_materialized: true" in output
    assert "overall_success: true" in output


def test_main_fails_when_selected_asset_is_not_marked_selected(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "launch_comic_remote_render_smoke.py",
        "launch_comic_remote_render_smoke_bad_selection_contract",
    )
    base_url = "http://127.0.0.1:8000"
    queue_url = (
        f"{base_url}/api/v1/comic/panels/panel-1/queue-renders"
        "?candidate_count=3&execution_mode=remote_worker"
    )
    jobs_url = f"{base_url}/api/v1/comic/panels/panel-1/render-jobs"
    select_url = f"{base_url}/api/v1/comic/panels/panel-1/assets/asset-2/select"
    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "Remote render smoke prompt",
            "lane": "adult_nsfw",
            "approval_token": "a" * 64,
            "anchor_render": {"prompt": "anchor prompt"},
            "resolved_cast": [],
            "location": {
                "id": "private-lounge",
                "name": "Private Lounge",
                "setting_anchor": "Quiet private lounge after closing.",
                "visual_rules": [],
                "restricted_elements": [],
                "match_note": "matched",
            },
            "episode_brief": {
                "title": "Night Intake",
                "logline": "Kaede pauses with a sealed invitation.",
                "core_conflict": "Decide whether to open the invitation.",
                "stakes": "Accepting changes the night.",
                "tone": "quiet tension",
            },
            "shots": [{"shot_no": 1, "beat": "Hook"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-remote-smoke-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
                "title": "Comic Remote Render Smoke",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [{"id": "panel-1", "panel_no": 1}],
                }
            ],
            "pages": [],
        },
        ("POST", queue_url): {
            "execution_mode": "remote_worker",
            "requested_count": 3,
            "queued_generation_count": 3,
            "materialized_asset_count": 0,
            "pending_render_job_count": 3,
            "remote_job_count": 3,
            "render_assets": [
                {"id": "asset-1", "storage_path": "", "is_selected": False},
                {"id": "asset-2", "storage_path": "", "is_selected": False},
                {"id": "asset-3", "storage_path": "", "is_selected": False},
            ],
        },
        ("POST", select_url): {
            "id": "asset-2",
            "scene_panel_id": "panel-1",
            "asset_role": "candidate",
            "storage_path": "images/comics/panel-1-a.png",
            "is_selected": False,
        },
    }
    jobs_responses = [
        [
            {
                "id": "job-2",
                "scene_panel_id": "panel-1",
                "render_asset_id": "asset-2",
                "generation_id": "gen-2",
                "request_index": 1,
                "source_id": "comic-panel-render:panel-1:3:remote_worker",
                "target_tool": "comic_panel_still",
                "executor_mode": "remote_worker",
                "executor_key": "default",
                "status": "completed",
                "request_json": {"comic": {"render_asset_id": "asset-2"}},
                "output_path": "images/comics/panel-1-a.png",
                "created_at": "2026-04-04T00:00:00+00:00",
                "updated_at": "2026-04-04T00:00:02+00:00",
            }
        ],
    ]

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url)
        if key == ("GET", jobs_url):
            return jobs_responses.pop(0)
        if key in responses:
            return responses[key]
        raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")

    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: _character_context(),
    )
    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_remote_render_smoke.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "queue_renders_success: false" in output
    assert "selected_panel_asset_count: 0" in output
    assert "real_selected_asset_materialized: false" in output
    assert "failed_step: queue_renders" in output
    assert "must be marked as selected" in output


def test_main_rejects_remote_backend_urls_for_remote_render_smoke(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "launch_comic_remote_render_smoke.py",
        "launch_comic_remote_render_smoke_remote_url",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_remote_render_smoke.py",
            "--base-url",
            "https://remote.example.com",
        ],
    )

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "import_success: false" in output
    assert "failed_step: bootstrap" in output
    assert "only supports local backend URLs" in output


def test_main_fails_when_queue_response_materializes_asset_but_not_remote_lane(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_script_module(
        "launch_comic_remote_render_smoke.py",
        "launch_comic_remote_render_smoke_false_positive",
    )
    base_url = "http://127.0.0.1:8000"
    queue_url = (
        f"{base_url}/api/v1/comic/panels/panel-1/queue-renders"
        "?candidate_count=3&execution_mode=remote_worker"
    )
    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "Remote render smoke prompt",
            "lane": "adult_nsfw",
            "approval_token": "a" * 64,
            "anchor_render": {"prompt": "anchor prompt"},
            "resolved_cast": [],
            "location": {
                "id": "private-lounge",
                "name": "Private Lounge",
                "setting_anchor": "Quiet private lounge after closing.",
                "visual_rules": [],
                "restricted_elements": [],
                "match_note": "matched",
            },
            "episode_brief": {
                "title": "Night Intake",
                "logline": "Kaede pauses with a sealed invitation.",
                "core_conflict": "Decide whether to open the invitation.",
                "stakes": "Accepting changes the night.",
                "tone": "quiet tension",
            },
            "shots": [{"shot_no": 1, "beat": "Hook"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-remote-smoke-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
                "title": "Comic Remote Render Smoke",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [{"id": "panel-1", "panel_no": 1}],
                }
            ],
            "pages": [],
        },
        ("POST", queue_url): {
            "execution_mode": "local_preview",
            "requested_count": 3,
            "queued_generation_count": 3,
            "materialized_asset_count": 1,
            "pending_render_job_count": 0,
            "remote_job_count": 0,
            "render_assets": [
                {
                    "id": "asset-2",
                    "storage_path": "images/comics/panel-1-a.png",
                    "is_selected": False,
                }
            ],
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url)
        if key in responses:
            return responses[key]
        raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")

    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: _character_context(),
    )
    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_remote_render_smoke.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 1

    output = capsys.readouterr().out
    assert "queue_renders_success: false" in output
    assert "failed_step: queue_renders" in output
    assert "did not stay on execution_mode=remote_worker" in output
