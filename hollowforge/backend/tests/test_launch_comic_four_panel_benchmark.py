from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_comic_four_panel_benchmark.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_four_panel_benchmark",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_recommend_execution_boundary_stays_local_when_budgets_hold() -> None:
    module = _load_module()

    recommendation = module._recommend_execution_boundary(
        {
            "overall_success": True,
            "total_duration_sec": 420.0,
            "panel_render_benchmarks": [
                {"panel_id": "panel-1", "render_duration_sec": 82.0},
                {"panel_id": "panel-2", "render_duration_sec": 91.0},
                {"panel_id": "panel-3", "render_duration_sec": 88.0},
                {"panel_id": "panel-4", "render_duration_sec": 95.0},
            ],
        },
        max_total_duration_sec=900.0,
        max_panel_render_duration_sec=180.0,
        max_average_panel_render_duration_sec=120.0,
    )

    assert recommendation["mode"] == "stay_local"
    assert recommendation["reasons"] == []


def test_recommend_execution_boundary_flags_remote_when_render_budget_breaks() -> None:
    module = _load_module()

    recommendation = module._recommend_execution_boundary(
        {
            "overall_success": True,
            "total_duration_sec": 1180.0,
            "panel_render_benchmarks": [
                {"panel_id": "panel-1", "render_duration_sec": 240.0},
                {"panel_id": "panel-2", "render_duration_sec": 245.0},
                {"panel_id": "panel-3", "render_duration_sec": 250.0},
                {"panel_id": "panel-4", "render_duration_sec": 255.0},
            ],
        },
        max_total_duration_sec=900.0,
        max_panel_render_duration_sec=180.0,
        max_average_panel_render_duration_sec=120.0,
    )

    assert recommendation["mode"] == "remote_worker_recommended"
    assert recommendation["average_panel_render_duration_sec"] == 247.5
    assert any("average panel render" in reason for reason in recommendation["reasons"])
    assert any("total duration" in reason for reason in recommendation["reasons"])


def test_recommend_execution_boundary_flags_remote_when_fail_fast_budget_hits() -> None:
    module = _load_module()

    recommendation = module._recommend_execution_boundary(
        {
            "overall_success": False,
            "failed_step": "queue_renders_budget_exceeded",
            "total_duration_sec": 181.5,
            "panel_render_benchmarks": [
                {"panel_id": "panel-1", "render_duration_sec": 181.0},
            ],
            "render_budget_exceeded_panel_id": "panel-1",
            "render_budget_exceeded_threshold_sec": 180.0,
            "render_budget_exceeded_value_sec": 181.0,
        },
        max_total_duration_sec=900.0,
        max_panel_render_duration_sec=180.0,
        max_average_panel_render_duration_sec=120.0,
    )

    assert recommendation["mode"] == "remote_worker_recommended"
    assert any("panel-1" in reason for reason in recommendation["reasons"])
    assert any("fail-fast budget" in reason for reason in recommendation["reasons"])


def test_run_benchmark_flow_tracks_four_panels_and_dialogues(
    monkeypatch,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"

    monkeypatch.setattr(
        module,
        "_now_monotonic",
        lambda: 0.0,
    )
    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: (
            {
                "id": "char_kaede_ren",
                "slug": "kaede-ren",
                "name": "Kaede Ren",
            },
            {
                "id": "charver_kaede_ren_still_v1",
                "character_id": "char_kaede_ren",
            },
            [{"id": "char_kaede_ren"}],
            [{"id": "charver_kaede_ren_still_v1"}],
        ),
    )

    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "benchmark story",
            "lane": "adult_nsfw",
            "policy_pack_id": "adult_nsfw_default",
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
                "premise": "Kaede tests throughput.",
                "continuity_guidance": ["Keep the same wardrobe."],
            },
            "shots": [
                {
                    "shot_no": 1,
                    "beat": "Beat 1",
                    "camera": "Camera 1",
                    "action": "Action 1",
                    "emotion": "Emotion 1",
                    "continuity_note": "Continuity 1",
                },
                {
                    "shot_no": 2,
                    "beat": "Beat 2",
                    "camera": "Camera 2",
                    "action": "Action 2",
                    "emotion": "Emotion 2",
                    "continuity_note": "Continuity 2",
                },
                {
                    "shot_no": 3,
                    "beat": "Beat 3",
                    "camera": "Camera 3",
                    "action": "Action 3",
                    "emotion": "Emotion 3",
                    "continuity_note": "Continuity 3",
                },
                {
                    "shot_no": 4,
                    "beat": "Beat 4",
                    "camera": "Camera 4",
                    "action": "Action 4",
                    "emotion": "Emotion 4",
                    "continuity_note": "Continuity 4",
                },
            ],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-bench-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [
                        {"id": "panel-1", "panel_no": 1},
                        {"id": "panel-2", "panel_no": 2},
                        {"id": "panel-3", "panel_no": 3},
                        {"id": "panel-4", "panel_no": 4},
                    ],
                }
            ],
            "pages": [],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-1/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-1a"}, {"id": "dlg-1b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-2/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-2a"}, {"id": "dlg-2b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-3/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-3a"}, {"id": "dlg-3b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-4/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-4a"}, {"id": "dlg-4b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-bench-1/pages/assemble"): {
            "episode_id": "comic-bench-1",
            "pages": [{"id": "page-1", "page_no": 1}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-bench-1/pages/export"): {
            "episode_id": "comic-bench-1",
            "pages": [{"id": "page-1", "page_no": 1, "export_state": "exported"}],
            "export_zip_path": "comics/exports/comic-bench-1_handoff.zip",
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)

    queued_panels: list[str] = []

    def fake_queue_and_select_panel_asset(**kwargs):  # type: ignore[no-untyped-def]
        panel_id = kwargs["panel_id"]
        queued_panels.append(panel_id)
        return (
            {
                "requested_count": 3,
                "queued_generation_count": 3,
                "render_assets": [
                    {
                        "id": f"asset-{panel_id}",
                        "storage_path": f"images/{panel_id}.png",
                        "is_selected": False,
                    }
                ],
            },
            {
                "id": f"asset-{panel_id}",
                "scene_panel_id": panel_id,
                "asset_role": "selected",
                "storage_path": f"images/{panel_id}.png",
                "is_selected": True,
            },
            False,
        )

    monkeypatch.setattr(
        module.comic_smoke,
        "_queue_and_select_panel_asset",
        fake_queue_and_select_panel_asset,
    )
    monkeypatch.setattr(
        module,
        "_run_production_dry_run",
        lambda **_: {
            "dry_run_success": True,
            "report_path": "comics/reports/comic-bench-1_dry_run.json",
            "page_count": 1,
            "selected_panel_asset_count": 4,
        },
    )

    summary = module._run_benchmark_flow(
        base_url=base_url,
        character_id=None,
        character_slug=None,
        character_version_id=None,
        story_prompt=module.DEFAULT_STORY_PROMPT,
        story_lane=module.DEFAULT_STORY_LANE,
        title=module.DEFAULT_TITLE,
        candidate_count=3,
        render_poll_attempts=5,
        render_poll_sec=0.1,
        layout_template_id=module.DEFAULT_LAYOUT_TEMPLATE_ID,
        manuscript_profile_id=module.DEFAULT_MANUSCRIPT_PROFILE_ID,
        max_panel_render_duration_sec=180.0,
    )

    assert summary["overall_success"] is True
    assert summary["panel_count"] == 4
    assert summary["selected_panel_asset_count"] == 4
    assert summary["generated_dialogue_count"] == 8
    assert queued_panels == ["panel-1", "panel-2", "panel-3", "panel-4"]
    assert len(summary["panel_render_benchmarks"]) == 4


def test_run_benchmark_flow_supports_remote_worker_and_layered_handoff_summary(
    monkeypatch,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"

    monkeypatch.setattr(
        module,
        "_now_monotonic",
        lambda: 0.0,
    )
    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: (
            {
                "id": "char_kaede_ren",
                "slug": "kaede-ren",
                "name": "Kaede Ren",
            },
            {
                "id": "charver_kaede_ren_still_v1",
                "character_id": "char_kaede_ren",
            },
            [{"id": "char_kaede_ren"}],
            [{"id": "charver_kaede_ren_still_v1"}],
        ),
    )

    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "benchmark story",
            "lane": "adult_nsfw",
            "policy_pack_id": "adult_nsfw_default",
            "approval_token": "a" * 64,
            "shots": [
                {"shot_no": 1},
                {"shot_no": 2},
                {"shot_no": 3},
                {"shot_no": 4},
            ],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-bench-remote-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [
                        {"id": "panel-1", "panel_no": 1},
                        {"id": "panel-2", "panel_no": 2},
                        {"id": "panel-3", "panel_no": 3},
                        {"id": "panel-4", "panel_no": 4},
                    ],
                }
            ],
            "pages": [],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-1/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-1a"}, {"id": "dlg-1b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-2/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-2a"}, {"id": "dlg-2b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-3/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-3a"}, {"id": "dlg-3b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-4/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-4a"}, {"id": "dlg-4b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-bench-remote-1/pages/assemble"): {
            "episode_id": "comic-bench-remote-1",
            "pages": [{"id": "page-1", "page_no": 1}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-bench-remote-1/pages/export"): {
            "episode_id": "comic-bench-remote-1",
            "pages": [{"id": "page-1", "page_no": 1, "export_state": "exported"}],
            "export_zip_path": "comics/exports/comic-bench-remote-1_handoff.zip",
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)

    remote_queue_calls: list[dict[str, object]] = []

    def fake_queue_and_select_remote_panel_asset(**kwargs):  # type: ignore[no-untyped-def]
        panel_id = str(kwargs["panel_id"])
        remote_queue_calls.append(kwargs)
        return (
            {
                "requested_count": 1,
                "queued_generation_count": 1,
                "execution_mode": "remote_worker",
                "remote_job_count": 1,
                "render_assets": [
                    {
                        "id": f"asset-{panel_id}",
                        "storage_path": f"images/{panel_id}.png",
                        "is_selected": False,
                    }
                ],
            },
            {
                "id": f"asset-{panel_id}",
                "scene_panel_id": panel_id,
                "asset_role": "selected",
                "storage_path": f"images/{panel_id}.png",
                "is_selected": True,
            },
            [
                {
                    "id": f"job-{panel_id}",
                    "render_asset_id": f"asset-{panel_id}",
                    "status": "completed",
                    "output_path": f"images/{panel_id}.png",
                }
            ],
        )

    monkeypatch.setattr(
        module,
        "remote_smoke",
        SimpleNamespace(
            _queue_and_select_remote_panel_asset=fake_queue_and_select_remote_panel_asset
        ),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "_run_production_dry_run",
        lambda **_: {
            "dry_run_success": True,
            "layered_package_verified": True,
            "layered_manifest_path": "comics/manifests/comic-bench-remote-1/manifest.json",
            "handoff_validation_path": "comics/manifests/comic-bench-remote-1/handoff_validation.json",
            "hard_block_count": 0,
            "report_path": "comics/reports/comic-bench-remote-1_dry_run.json",
            "page_count": 1,
            "selected_panel_asset_count": 4,
            "export_zip_path": "comics/exports/comic-bench-remote-1_handoff.zip",
        },
    )

    summary = module._run_benchmark_flow(
        base_url=base_url,
        character_id=None,
        character_slug=None,
        character_version_id=None,
        story_prompt=module.DEFAULT_STORY_PROMPT,
        story_lane=module.DEFAULT_STORY_LANE,
        title=module.DEFAULT_TITLE,
        candidate_count=1,
        execution_mode="remote_worker",
        render_poll_attempts=5,
        render_poll_sec=0.1,
        layout_template_id=module.DEFAULT_LAYOUT_TEMPLATE_ID,
        manuscript_profile_id=module.DEFAULT_MANUSCRIPT_PROFILE_ID,
        max_panel_render_duration_sec=180.0,
    )

    assert summary["overall_success"] is True
    assert summary["execution_mode"] == "remote_worker"
    assert summary["selected_panel_asset_count"] == 4
    assert summary["materialized_asset_count"] == 4
    assert summary["layered_package_verified"] is True
    assert (
        summary["layered_manifest_path"]
        == "comics/manifests/comic-bench-remote-1/manifest.json"
    )
    assert (
        summary["handoff_validation_path"]
        == "comics/manifests/comic-bench-remote-1/handoff_validation.json"
    )
    assert summary["hard_block_count"] == 0
    assert summary["dry_run_report_path"] == "comics/reports/comic-bench-remote-1_dry_run.json"
    assert [call["panel_id"] for call in remote_queue_calls] == [
        "panel-1",
        "panel-2",
        "panel-3",
        "panel-4",
    ]
    assert all(call["candidate_count"] == 1 for call in remote_queue_calls)


def test_run_benchmark_flow_fails_fast_when_panel_render_budget_breaks(
    monkeypatch,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"

    monotonic_values = iter([0.0, 12.0])
    monkeypatch.setattr(module, "_now_monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: (
            {
                "id": "char_kaede_ren",
                "slug": "kaede-ren",
                "name": "Kaede Ren",
            },
            {
                "id": "charver_kaede_ren_still_v1",
                "character_id": "char_kaede_ren",
            },
            [{"id": "char_kaede_ren"}],
            [{"id": "charver_kaede_ren_still_v1"}],
        ),
    )

    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "benchmark story",
            "lane": "adult_nsfw",
            "policy_pack_id": "adult_nsfw_default",
            "approval_token": "a" * 64,
            "shots": [
                {"shot_no": 1},
                {"shot_no": 2},
                {"shot_no": 3},
                {"shot_no": 4},
            ],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-bench-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [
                        {"id": "panel-1", "panel_no": 1},
                        {"id": "panel-2", "panel_no": 2},
                        {"id": "panel-3", "panel_no": 3},
                        {"id": "panel-4", "panel_no": 4},
                    ],
                }
            ],
            "pages": [],
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    queued_panels: list[str] = []

    def fake_queue_and_select_panel_asset(**kwargs):  # type: ignore[no-untyped-def]
        panel_id = kwargs["panel_id"]
        queued_panels.append(panel_id)
        return (
            {
                "requested_count": 3,
                "queued_generation_count": 3,
                "render_assets": [
                    {
                        "id": f"asset-{panel_id}",
                        "storage_path": f"images/{panel_id}.png",
                        "is_selected": False,
                    }
                ],
            },
            {
                "id": f"asset-{panel_id}",
                "scene_panel_id": panel_id,
                "asset_role": "selected",
                "storage_path": f"images/{panel_id}.png",
                "is_selected": True,
            },
            False,
        )

    def fake_measure_call(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        if fn is module.comic_smoke._request_json:
            return fake_request_json(*args, **kwargs), 0.05
        if fn is module.comic_smoke._queue_and_select_panel_asset:
            return fake_queue_and_select_panel_asset(**kwargs), 181.0
        raise AssertionError(f"Unexpected measured call: {fn!r}")

    monkeypatch.setattr(module, "_measure_call", fake_measure_call)
    monkeypatch.setattr(
        module.comic_smoke,
        "_request_json",
        fake_request_json,
    )
    monkeypatch.setattr(
        module.comic_smoke,
        "_queue_and_select_panel_asset",
        fake_queue_and_select_panel_asset,
    )
    monkeypatch.setattr(
        module,
        "_run_production_dry_run",
        lambda **_: pytest.fail("dry-run should not execute after fail-fast"),
    )

    with pytest.raises(module.BenchmarkExecutionError) as exc_info:
        module._run_benchmark_flow(
            base_url=base_url,
            character_id=None,
            character_slug=None,
            character_version_id=None,
            story_prompt=module.DEFAULT_STORY_PROMPT,
            story_lane=module.DEFAULT_STORY_LANE,
            title=module.DEFAULT_TITLE,
            candidate_count=3,
            fail_fast_on_budget_exceed=True,
            render_poll_attempts=5,
            render_poll_sec=0.1,
            layout_template_id=module.DEFAULT_LAYOUT_TEMPLATE_ID,
            manuscript_profile_id=module.DEFAULT_MANUSCRIPT_PROFILE_ID,
            max_panel_render_duration_sec=180.0,
        )

    summary = exc_info.value.summary
    assert summary["failed_step"] == "queue_renders_budget_exceeded"
    assert summary["render_budget_exceeded_panel_id"] == "panel-1"
    assert summary["render_budget_exceeded_threshold_sec"] == 180.0
    assert summary["render_budget_exceeded_value_sec"] == 181.0
    assert summary["selected_panel_asset_count"] == 1
    assert queued_panels == ["panel-1"]


def test_run_benchmark_flow_continues_when_budget_breaks_but_fail_fast_is_disabled(
    monkeypatch,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"

    monkeypatch.setattr(module, "_now_monotonic", lambda: 0.0)
    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: (
            {
                "id": "char_kaede_ren",
                "slug": "kaede-ren",
                "name": "Kaede Ren",
            },
            {
                "id": "charver_kaede_ren_still_v1",
                "character_id": "char_kaede_ren",
            },
            [{"id": "char_kaede_ren"}],
            [{"id": "charver_kaede_ren_still_v1"}],
        ),
    )

    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "benchmark story",
            "lane": "adult_nsfw",
            "policy_pack_id": "adult_nsfw_default",
            "approval_token": "a" * 64,
            "shots": [
                {"shot_no": 1},
                {"shot_no": 2},
                {"shot_no": 3},
                {"shot_no": 4},
            ],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-bench-continue-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [
                        {"id": "panel-1", "panel_no": 1},
                        {"id": "panel-2", "panel_no": 2},
                        {"id": "panel-3", "panel_no": 3},
                        {"id": "panel-4", "panel_no": 4},
                    ],
                }
            ],
            "pages": [],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-1/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-1a"}, {"id": "dlg-1b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-2/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-2a"}, {"id": "dlg-2b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-3/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-3a"}, {"id": "dlg-3b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-4/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-4a"}, {"id": "dlg-4b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-bench-continue-1/pages/assemble"): {
            "episode_id": "comic-bench-continue-1",
            "pages": [{"id": "page-1", "page_no": 1}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-bench-continue-1/pages/export"): {
            "episode_id": "comic-bench-continue-1",
            "pages": [{"id": "page-1", "page_no": 1, "export_state": "exported"}],
            "export_zip_path": "comics/exports/comic-bench-continue-1_handoff.zip",
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    queued_panels: list[str] = []

    def fake_queue_and_select_panel_asset(**kwargs):  # type: ignore[no-untyped-def]
        panel_id = kwargs["panel_id"]
        queued_panels.append(panel_id)
        return (
            {
                "requested_count": 1,
                "queued_generation_count": 1,
                "render_assets": [
                    {
                        "id": f"asset-{panel_id}",
                        "storage_path": f"images/{panel_id}.png",
                        "is_selected": False,
                    }
                ],
            },
            {
                "id": f"asset-{panel_id}",
                "scene_panel_id": panel_id,
                "asset_role": "selected",
                "storage_path": f"images/{panel_id}.png",
                "is_selected": True,
            },
            False,
        )

    render_durations = iter([181.0, 182.0, 183.0, 184.0])

    def fake_measure_call(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
        if fn is module.comic_smoke._request_json:
            return fake_request_json(*args, **kwargs), 0.05
        if fn is module.comic_smoke._queue_and_select_panel_asset:
            return fake_queue_and_select_panel_asset(**kwargs), next(render_durations)
        if fn is module._run_production_dry_run:
            return (
                {
                    "dry_run_success": True,
                    "page_count": 1,
                    "selected_panel_asset_count": 4,
                    "report_path": "comics/reports/comic-bench-continue-1_dry_run.json",
                    "layered_package_verified": True,
                    "layered_manifest_path": "comics/manifests/comic-bench-continue-1/manifest.json",
                    "handoff_validation_path": "comics/manifests/comic-bench-continue-1/handoff_validation.json",
                    "hard_block_count": 0,
                },
                0.2,
            )
        raise AssertionError(f"Unexpected measured call: {fn!r}")

    monkeypatch.setattr(module, "_measure_call", fake_measure_call)
    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(
        module.comic_smoke,
        "_queue_and_select_panel_asset",
        fake_queue_and_select_panel_asset,
    )

    summary = module._run_benchmark_flow(
        base_url=base_url,
        character_id=None,
        character_slug=None,
        character_version_id=None,
        story_prompt=module.DEFAULT_STORY_PROMPT,
        story_lane=module.DEFAULT_STORY_LANE,
        title=module.DEFAULT_TITLE,
        candidate_count=1,
        execution_mode="local_preview",
        fail_fast_on_budget_exceed=False,
        render_poll_attempts=5,
        render_poll_sec=0.1,
        layout_template_id=module.DEFAULT_LAYOUT_TEMPLATE_ID,
        manuscript_profile_id=module.DEFAULT_MANUSCRIPT_PROFILE_ID,
        max_panel_render_duration_sec=180.0,
    )

    assert summary["overall_success"] is True
    assert summary["queue_renders_success"] is True
    assert summary["selected_panel_asset_count"] == 4
    assert summary["average_panel_render_duration_sec"] == 182.5
    assert summary["render_budget_exceeded_panel_id"] == "panel-1"
    assert summary["render_budget_exceeded_value_sec"] == 181.0
    assert queued_panels == ["panel-1", "panel-2", "panel-3", "panel-4"]


def test_main_writes_report_and_prints_remote_recommendation(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    module = _load_module()
    monkeypatch.setattr(module.settings, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(module.settings, "COMICS_DIR", module.settings.DATA_DIR / "comics")
    module.settings.COMICS_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        module,
        "_run_benchmark_flow",
        lambda **_: {
            "base_url": "http://127.0.0.1:8000",
            "episode_id": "comic-bench-1",
            "panel_count": 4,
            "selected_panel_asset_count": 4,
            "page_count": 1,
            "dry_run_success": True,
            "overall_success": True,
            "total_duration_sec": 1200.0,
            "panel_render_benchmarks": [
                {"panel_id": "panel-1", "render_duration_sec": 240.0},
                {"panel_id": "panel-2", "render_duration_sec": 240.0},
                {"panel_id": "panel-3", "render_duration_sec": 240.0},
                {"panel_id": "panel-4", "render_duration_sec": 240.0},
            ],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_four_panel_benchmark.py",
            "--base-url",
            "http://127.0.0.1:8000",
        ],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    assert "overall_success: true" in captured.out
    assert "recommendation_mode: remote_worker_recommended" in captured.out
    assert "benchmark_report_path: comics/reports/" in captured.out

    report_paths = list(module.settings.COMICS_REPORTS_DIR.glob("*_local_benchmark.json"))
    assert len(report_paths) == 1
    report = json.loads(report_paths[0].read_text(encoding="utf-8"))
    assert report["episode_id"] == "comic-bench-1"
    assert report["recommendation"]["mode"] == "remote_worker_recommended"
    assert report["panel_count"] == 4


def test_main_uses_extended_render_poll_budget_by_default(
    monkeypatch,
) -> None:
    module = _load_module()
    captured: dict[str, object] = {}

    def fake_run_benchmark_flow(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return {
            "base_url": "http://127.0.0.1:8000",
            "episode_id": "comic-bench-1",
            "panel_count": 4,
            "selected_panel_asset_count": 4,
            "page_count": 1,
            "dry_run_success": True,
            "overall_success": True,
            "total_duration_sec": 100.0,
            "panel_render_benchmarks": [
                {"panel_id": "panel-1", "render_duration_sec": 25.0},
                {"panel_id": "panel-2", "render_duration_sec": 25.0},
                {"panel_id": "panel-3", "render_duration_sec": 25.0},
                {"panel_id": "panel-4", "render_duration_sec": 25.0},
            ],
        }

    monkeypatch.setattr(module, "_run_benchmark_flow", fake_run_benchmark_flow)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_four_panel_benchmark.py",
            "--base-url",
            "http://127.0.0.1:8000",
        ],
    )

    assert module.main() == 0
    assert captured["candidate_count"] == 1
    assert captured["execution_mode"] == "remote_worker"
    assert captured["fail_fast_on_budget_exceed"] is False
    assert captured["render_poll_attempts"] == 360
    assert captured["max_panel_render_duration_sec"] == 180.0
