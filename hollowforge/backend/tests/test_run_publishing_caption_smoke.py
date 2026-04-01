from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_publishing_caption_smoke.py"
    spec = importlib.util.spec_from_file_location("run_publishing_caption_smoke", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_main(module, argv: list[str], request_json):  # type: ignore[no-untyped-def]
    original_argv = sys.argv
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        sys.argv = argv
        module._request_json = request_json
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = module.main()
    finally:
        sys.argv = original_argv
    return exit_code, stdout.getvalue(), stderr.getvalue()


def test_readiness_only_mode_reports_full_without_generating_caption() -> None:
    module = _load_module()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url, payload))
        if url.endswith("/api/v1/publishing/readiness"):
            return {
                "caption_generation_ready": True,
                "draft_publish_ready": True,
                "degraded_mode": "full",
                "provider": "openrouter",
                "model": "x-ai/grok-2-vision-1212",
                "missing_requirements": [],
                "notes": [],
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "run_publishing_caption_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--generation-id",
            "generation-123",
            "--readiness-only",
        ],
        fake_request_json,
    )

    assert exit_code == 0
    assert stderr == ""
    assert "readiness_mode: full" in stdout
    assert "caption_id:" not in stdout
    assert all(not url.endswith("/captions/generate") for _, url, _ in calls)


def test_smoke_fails_fast_when_readiness_is_not_full() -> None:
    module = _load_module()

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        if url.endswith("/api/v1/publishing/readiness"):
            return {
                "caption_generation_ready": False,
                "draft_publish_ready": True,
                "degraded_mode": "draft_only",
                "provider": "openrouter",
                "model": "x-ai/grok-2-vision-1212",
                "missing_requirements": ["OPENROUTER_API_KEY"],
                "notes": [],
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "run_publishing_caption_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--generation-id",
            "generation-123",
        ],
        fake_request_json,
    )

    assert exit_code == 1
    assert "draft_only" in stdout + stderr


def test_smoke_reports_created_caption_metadata() -> None:
    module = _load_module()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url, payload))
        if url.endswith("/api/v1/publishing/readiness"):
            return {
                "caption_generation_ready": True,
                "draft_publish_ready": True,
                "degraded_mode": "full",
                "provider": "openrouter",
                "model": "x-ai/grok-2-vision-1212",
                "missing_requirements": [],
                "notes": [],
            }
        if url.endswith("/api/v1/publishing/generations/generation-123/captions/generate"):
            assert payload == {
                "platform": "pixiv",
                "tone": "teaser",
                "channel": "social_short",
                "approved": False,
            }
            return {
                "id": "caption-123",
                "generation_id": "generation-123",
                "channel": "social_short",
                "platform": "pixiv",
                "provider": "openrouter",
                "model": "x-ai/grok-2-vision-1212",
                "prompt_version": "v1",
                "tone": "teaser",
                "story": "caption story",
                "hashtags": "#smoke",
                "approved": False,
                "created_at": "2026-04-01T00:00:00Z",
                "updated_at": "2026-04-01T00:00:00Z",
            }
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "run_publishing_caption_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--generation-id",
            "generation-123",
            "--platform",
            "pixiv",
            "--tone",
            "teaser",
            "--channel",
            "social_short",
        ],
        fake_request_json,
    )

    assert exit_code == 0
    assert stderr == ""
    assert "caption_id: caption-123" in stdout
    assert "provider: openrouter" in stdout
    assert "model: x-ai/grok-2-vision-1212" in stdout
    assert "generation_id: generation-123" in stdout
    assert "approved: false" in stdout
    assert [call[1] for call in calls] == [
        "http://127.0.0.1:8000/api/v1/publishing/readiness",
        "http://127.0.0.1:8000/api/v1/publishing/generations/generation-123/captions/generate",
    ]
