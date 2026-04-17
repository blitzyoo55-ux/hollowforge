from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "launch_comic_mvp_smoke.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_mvp_smoke",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_responses(
    base_url: str,
    *,
    first_panel_storage_path: str = "",
    second_panel_storage_path: str = "images/panel-2-a.png",
) -> dict[tuple[str, str], object]:
    return {
        ("GET", f"{base_url}/api/v1/comic/characters"): [
            {
                "id": "char_kaede_ren",
                "slug": "kaede-ren",
                "name": "Kaede Ren",
                "status": "active",
                "tier": "hero",
            }
        ],
        ("GET", f"{base_url}/api/v1/comic/character-versions"): [
            {
                "id": "charver_kaede_ren_still_v1",
                "character_id": "char_kaede_ren",
                "version_name": "Still v1",
                "purpose": "comic_mvp",
                "checkpoint": "waiIllustriousSDXL_v160.safetensors",
                "workflow_lane": "sdxl_illustrious",
            }
        ],
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "Smoke story prompt",
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
                },
                {
                    "shot_no": 2,
                    "beat": "Escalate the tension",
                    "camera": "Profile shot.",
                    "action": "She turns the invitation in her hand.",
                    "emotion": "Guarded interest",
                    "continuity_note": "Preserve lounge continuity.",
                },
                {
                    "shot_no": 3,
                    "beat": "Reveal the key detail",
                    "camera": "Over-the-shoulder close-up.",
                    "action": "The seal catches the light.",
                    "emotion": "Focused concern",
                    "continuity_note": "Same framing language.",
                },
                {
                    "shot_no": 4,
                    "beat": "Close on a decision",
                    "camera": "Tight two-shot.",
                    "action": "Kaede commits to opening it.",
                    "emotion": "Controlled resolve",
                    "continuity_note": "Stay in the same location.",
                },
            ],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-ep-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
                "title": "Night Intake",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [
                        {"id": "panel-1", "panel_no": 1},
                        {"id": "panel-2", "panel_no": 2},
                    ],
                }
            ],
            "pages": [],
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/panels/panel-1/queue-renders?candidate_count=3",
        ): {
            "requested_count": 3,
            "queued_generation_count": 3,
            "render_assets": [
                {"id": "asset-1", "is_selected": False, "storage_path": first_panel_storage_path},
                {"id": "asset-2", "is_selected": False, "storage_path": ""},
                {"id": "asset-3", "is_selected": False, "storage_path": ""},
            ],
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/panels/panel-1/assets/asset-1/select",
        ): {
            "id": "asset-1",
            "scene_panel_id": "panel-1",
            "asset_role": "selected",
            "storage_path": "images/panel-1-a.png",
            "is_selected": True,
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/panels/panel-2/queue-renders?candidate_count=3",
        ): {
            "requested_count": 3,
            "queued_generation_count": 3,
            "render_assets": [
                {"id": "asset-4", "is_selected": False, "storage_path": second_panel_storage_path},
                {"id": "asset-5", "is_selected": False, "storage_path": ""},
                {"id": "asset-6", "is_selected": False, "storage_path": ""},
            ],
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/panels/panel-2/assets/asset-4/select",
        ): {
            "id": "asset-4",
            "scene_panel_id": "panel-2",
            "asset_role": "selected",
            "storage_path": "images/panel-2-a.png",
            "is_selected": True,
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-1/dialogues/generate"): {
            "generated_count": 3,
            "dialogues": [
                {"id": "dlg-1"},
                {"id": "dlg-2"},
                {"id": "dlg-3"},
            ],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-ep-1/pages/assemble"): {
            "layout_template_id": "jp_2x2_v1",
            "pages": [
                {
                    "id": "page-1",
                    "page_no": 1,
                    "preview_path": "comics/previews/comic-ep-1_page_01.png",
                }
            ],
            "export_manifest_path": "comics/manifests/comic-ep-1_pages.json",
            "dialogue_json_path": "comics/manifests/comic-ep-1_dialogues.json",
            "panel_asset_manifest_path": "comics/manifests/comic-ep-1_panel_assets.json",
            "page_assembly_manifest_path": "comics/manifests/comic-ep-1_pages.json",
            "teaser_handoff_manifest_path": "comics/manifests/comic-ep-1_teaser_handoff.json",
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-ep-1/pages/export"): {
            "layout_template_id": "jp_2x2_v1",
            "pages": [
                {
                    "id": "page-1",
                    "page_no": 1,
                    "preview_path": "comics/previews/comic-ep-1_page_01.png",
                    "export_state": "exported",
                }
            ],
            "export_manifest_path": "comics/manifests/comic-ep-1_pages.json",
            "dialogue_json_path": "comics/manifests/comic-ep-1_dialogues.json",
            "panel_asset_manifest_path": "comics/manifests/comic-ep-1_panel_assets.json",
            "page_assembly_manifest_path": "comics/manifests/comic-ep-1_pages.json",
            "teaser_handoff_manifest_path": "comics/manifests/comic-ep-1_teaser_handoff.json",
            "export_zip_path": "comics/exports/comic-ep-1_handoff.zip",
        },
        ("GET", f"{base_url}/api/v1/comic/episodes/comic-ep-1"): {
            "episode": {"id": "comic-ep-1"},
            "scenes": [{"scene": {"id": "scene-1"}, "panels": [{"id": "panel-1"}]}],
            "pages": [{"id": "page-1"}],
        },
    }


def test_main_prints_success_markers_for_bounded_comic_flow(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"
    responses = _build_responses(base_url)

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url)
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        module,
        "_write_synthetic_asset_preview",
        lambda *, panel_id, asset_id: f"comics/previews/smoke_assets/{panel_id}_{asset_id}.png",
    )
    monkeypatch.setattr(module, "_bind_asset_storage_path", lambda *, asset_id, storage_path: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_mvp_smoke.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    assert "import_success: true" in captured.out
    assert "episode_id: comic-ep-1" in captured.out
    assert "queue_renders_success: true" in captured.out
    assert "synthetic_asset_fallback_used: true" in captured.out
    assert "export_success: true" in captured.out
    assert "overall_success: true" in captured.out
    assert "selected_panel_asset_count: 2" in captured.out


def test_main_rejects_synthetic_fallback_for_remote_backend_urls(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "https://remote.example.com"
    responses = _build_responses(base_url)

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url)
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_mvp_smoke.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 1

    captured = capsys.readouterr()
    assert "queue_renders_success: false" in captured.out
    assert "failed_step: queue_renders" in captured.out
    assert "Synthetic asset fallback is only supported for local backend URLs" in captured.out
