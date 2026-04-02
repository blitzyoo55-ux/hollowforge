from __future__ import annotations

import importlib.util
import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "launch_story_planner_smoke.py"
    spec = importlib.util.spec_from_file_location("launch_story_planner_smoke", module_path)
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


def _catalog_result() -> dict[str, object]:
    return {
        "characters": [{"id": "hana_seo"}],
        "locations": [{"id": "moonlit_bathhouse"}],
        "policy_packs": [{"id": "canon_adult_nsfw_v1"}],
    }


def _plan_result(*, recommended_anchor_shot_no: object, recommended_anchor_reason: object) -> dict[str, object]:
    return {
        "lane": "adult_nsfw",
        "policy_pack_id": "canon_adult_nsfw_v1",
        "location": {"name": "Moonlit Bathhouse Corridor"},
        "shots": [{"shot_no": 1}, {"shot_no": 2}, {"shot_no": 3}, {"shot_no": 4}],
        "recommended_anchor_shot_no": recommended_anchor_shot_no,
        "recommended_anchor_reason": recommended_anchor_reason,
    }


def _queue_result() -> dict[str, object]:
    return {
        "lane": "adult_nsfw",
        "requested_shot_count": 4,
        "queued_generation_count": 8,
        "queued_shots": [
            {"shot_no": 1, "generation_ids": ["gen-s1-c1", "gen-s1-c2"]},
            {"shot_no": 2, "generation_ids": ["gen-s2-c1", "gen-s2-c2"]},
            {"shot_no": 3, "generation_ids": ["gen-s3-c1", "gen-s3-c2"]},
            {"shot_no": 4, "generation_ids": ["gen-s4-c1", "gen-s4-c2"]},
        ],
    }


def _queue_result_without_recommended_shot() -> dict[str, object]:
    return {
        "lane": "adult_nsfw",
        "requested_shot_count": 4,
        "queued_generation_count": 6,
        "queued_shots": [
            {"shot_no": 1, "generation_ids": ["gen-s1-c1", "gen-s1-c2"]},
            {"shot_no": 2, "generation_ids": ["gen-s2-c1", "gen-s2-c2"]},
            {"shot_no": 4, "generation_ids": ["gen-s4-c1", "gen-s4-c2"]},
        ],
    }


def _queue_result_with_empty_generation_ids() -> dict[str, object]:
    return {
        "lane": "adult_nsfw",
        "requested_shot_count": 4,
        "queued_generation_count": 6,
        "queued_shots": [
            {"shot_no": 1, "generation_ids": ["gen-s1-c1", "gen-s1-c2"]},
            {"shot_no": 2, "generation_ids": ["gen-s2-c1", "gen-s2-c2"]},
            {"shot_no": 3, "generation_ids": []},
            {"shot_no": 4, "generation_ids": ["gen-s4-c1", "gen-s4-c2"]},
        ],
    }


def test_omitted_support_description_only_sends_lead_cast() -> None:
    module = _load_module()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url, payload))
        if url.endswith("/api/v1/tools/story-planner/catalog"):
            return _catalog_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            assert payload == {
                "story_prompt": "Hana Seo compares notes with a quiet messenger.",
                "lane": "adult_nsfw",
                "cast": [
                    {
                        "role": "lead",
                        "source_type": "registry",
                        "character_id": "hana_seo",
                    }
                ],
            }
            return _plan_result(
                recommended_anchor_shot_no=2,
                recommended_anchor_reason="Lead/support exchange reads strongest at shot 2.",
            )
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return _queue_result()
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "launch_story_planner_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--story-prompt",
            "Hana Seo compares notes with a quiet messenger.",
            "--lane",
            "adult_nsfw",
            "--candidate-count",
            "2",
            "--lead-character-id",
            "hana_seo",
        ],
        fake_request_json,
    )

    assert exit_code == 0
    assert stderr == ""
    assert all(
        payload is None or "freeform_description" not in payload.get("cast", [{}])[0]
        for _, _, payload in calls
        if payload is not None and isinstance(payload, dict) and "cast" in payload
    )
    assert "planner_recommendation:" in stdout
    assert "recommended_anchor_shot_no: 2" in stdout
    assert "recommended_shot_generations:" in stdout


def test_blank_support_description_is_treated_like_omitted_support_description() -> None:
    module = _load_module()
    captured_payloads: list[dict[str, object]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        if url.endswith("/api/v1/tools/story-planner/catalog"):
            return _catalog_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            assert payload is not None
            captured_payloads.append(payload)
            return _plan_result(
                recommended_anchor_shot_no=2,
                recommended_anchor_reason="Lead/support exchange reads strongest at shot 2.",
            )
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return _queue_result()
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "launch_story_planner_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--story-prompt",
            "Hana Seo compares notes with a quiet messenger.",
            "--lane",
            "adult_nsfw",
            "--candidate-count",
            "2",
            "--lead-character-id",
            "hana_seo",
            "--support-description",
            "",
        ],
        fake_request_json,
    )

    assert exit_code == 0
    assert stderr == ""
    assert captured_payloads == [
        {
            "story_prompt": "Hana Seo compares notes with a quiet messenger.",
            "lane": "adult_nsfw",
            "cast": [
                {
                    "role": "lead",
                    "source_type": "registry",
                    "character_id": "hana_seo",
                }
            ],
        }
    ]
    assert "recommended_anchor_shot_no: 2" in stdout


def test_explicit_support_description_passes_through_exactly() -> None:
    module = _load_module()
    captured_payloads: list[dict[str, object]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        if url.endswith("/api/v1/tools/story-planner/catalog"):
            return _catalog_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            assert payload is not None
            captured_payloads.append(payload)
            return _plan_result(
                recommended_anchor_shot_no=3,
                recommended_anchor_reason="Shot 3 best fits the reveal beat.",
            )
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return _queue_result()
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "launch_story_planner_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--story-prompt",
            "Hana Seo compares notes with a quiet messenger.",
            "--lane",
            "adult_nsfw",
            "--candidate-count",
            "2",
            "--lead-character-id",
            "hana_seo",
            "--support-description",
            "quiet messenger in a dark coat",
        ],
        fake_request_json,
    )

    assert exit_code == 0
    assert stderr == ""
    assert captured_payloads == [
        {
            "story_prompt": "Hana Seo compares notes with a quiet messenger.",
            "lane": "adult_nsfw",
            "cast": [
                {
                    "role": "lead",
                    "source_type": "registry",
                    "character_id": "hana_seo",
                },
                {
                    "role": "support",
                    "source_type": "freeform",
                    "freeform_description": "quiet messenger in a dark coat",
                },
            ],
        }
    ]
    assert "recommended_anchor_shot_no: 3" in stdout
    assert "recommended_anchor_reason: Shot 3 best fits the reveal beat." in stdout


def test_recommendation_section_precedes_full_queue_summary_and_uses_queued_shots() -> None:
    module = _load_module()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url, payload))
        if url.endswith("/api/v1/tools/story-planner/catalog"):
            return _catalog_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            return _plan_result(
                recommended_anchor_shot_no=3,
                recommended_anchor_reason="Shot 3 best fits the reveal beat.",
            )
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return _queue_result()
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "launch_story_planner_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--story-prompt",
            "Hana Seo compares notes with a quiet messenger.",
            "--lane",
            "adult_nsfw",
            "--candidate-count",
            "2",
            "--lead-character-id",
            "hana_seo",
        ],
        fake_request_json,
    )

    assert exit_code == 0
    assert stderr == ""
    assert "planner_recommendation:" in stdout
    assert "recommended_anchor_shot_no: 3" in stdout
    assert "recommended_anchor_reason: Shot 3 best fits the reveal beat." in stdout
    assert "recommended_shot_generations:" in stdout
    assert "shot_03: ['gen-s3-c1', 'gen-s3-c2']" in stdout
    assert stdout.index("recommended_shot_generations:") < stdout.index("queue_result:")
    assert stdout.index("queue_result:") < stdout.index("shot_01: ['gen-s1-c1', 'gen-s1-c2']")
    assert [method for method, _, _ in calls] == ["GET", "POST", "POST"]


@pytest.mark.parametrize(
    "recommended_anchor_shot_no, recommended_anchor_reason, expected_error",
    [
        (None, "Shot 3 best fits the reveal beat.", "recommended_anchor_shot_no"),
        ("not-a-number", "Shot 3 best fits the reveal beat.", "recommended_anchor_shot_no"),
        (3, "", "recommended_anchor_reason"),
    ],
)
def test_invalid_or_missing_recommendation_fails_loudly(
    recommended_anchor_shot_no: object,
    recommended_anchor_reason: object,
    expected_error: str,
) -> None:
    module = _load_module()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url, payload))
        if url.endswith("/api/v1/tools/story-planner/catalog"):
            return _catalog_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            return _plan_result(
                recommended_anchor_shot_no=recommended_anchor_shot_no,
                recommended_anchor_reason=recommended_anchor_reason,
            )
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            raise AssertionError("queue request should not run when recommendation is invalid")
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "launch_story_planner_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--story-prompt",
            "Hana Seo compares notes with a quiet messenger.",
            "--lane",
            "adult_nsfw",
            "--candidate-count",
            "2",
            "--lead-character-id",
            "hana_seo",
        ],
        fake_request_json,
    )

    assert exit_code == 1
    assert "plan_result:" in stdout
    assert "queue_result:" not in stdout
    assert "planner_recommendation:" not in stdout
    assert expected_error in stderr
    assert [method for method, _, _ in calls] == ["GET", "POST"]


@pytest.mark.parametrize(
    "queue_result_factory, expected_error",
    [
        (_queue_result_without_recommended_shot, "queued shots for the recommended anchor shot"),
        (_queue_result_with_empty_generation_ids, "generation_ids for the recommended anchor shot"),
    ],
)
def test_queue_side_validation_failures_are_reported_loudly(
    queue_result_factory,
    expected_error: str,
) -> None:
    module = _load_module()
    calls: list[tuple[str, str, dict[str, object] | None]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append((method, url, payload))
        if url.endswith("/api/v1/tools/story-planner/catalog"):
            return _catalog_result()
        if url.endswith("/api/v1/tools/story-planner/plan"):
            return _plan_result(
                recommended_anchor_shot_no=3,
                recommended_anchor_reason="Shot 3 best fits the reveal beat.",
            )
        if url.endswith("/api/v1/tools/story-planner/generate-anchors"):
            return queue_result_factory()
        raise AssertionError(f"unexpected request: {method} {url}")

    exit_code, stdout, stderr = _run_main(
        module,
        [
            "launch_story_planner_smoke.py",
            "--base-url",
            "http://127.0.0.1:8000",
            "--story-prompt",
            "Hana Seo compares notes with a quiet messenger.",
            "--lane",
            "adult_nsfw",
            "--candidate-count",
            "2",
            "--lead-character-id",
            "hana_seo",
        ],
        fake_request_json,
    )

    assert exit_code == 1
    assert "plan_result:" in stdout
    assert "planner_recommendation:" not in stdout
    assert "queue_result:" not in stdout
    assert expected_error in stderr
    assert [method for method, _, _ in calls] == ["GET", "POST", "POST"]
