from __future__ import annotations

import json

import pytest

from app.services.comic_render_dispatch_service import (
    build_comic_remote_worker_payload,
)


def test_build_comic_remote_worker_payload_includes_generation_and_comic_lineage() -> None:
    payload = build_comic_remote_worker_payload(
        {
            "id": "comic-job-1",
            "generation_id": "gen-1",
            "target_tool": "comic_panel_still",
            "executor_mode": "remote_worker",
            "executor_key": "default",
            "request_json": json.dumps(
                {
                    "backend_family": "sdxl_still",
                    "model_profile": "comic_panel_sdxl_v1",
                }
            ),
        },
        {
            "id": "gen-1",
            "prompt": "panel prompt",
            "negative_prompt": "bad anatomy",
            "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
            "loras": json.dumps(
                [{"filename": "kaede_face.safetensors", "strength": 0.85}]
            ),
            "steps": 34,
            "cfg": 5.5,
            "width": 832,
            "height": 1216,
            "sampler": "euler_ancestral",
            "scheduler": "normal",
            "clip_skip": 2,
            "source_id": "comic-panel-render:panel-1:3:remote_worker",
            "created_at": "2026-04-04T00:00:00+00:00",
        },
        {
            "id": "asset-1",
            "scene_panel_id": "panel-1",
        },
        {
            "character_version_id": "charver_kaede_ren_still_v1",
        },
    )

    assert payload["hollowforge_job_id"] == "comic-job-1"
    assert payload["target_tool"] == "comic_panel_still"
    assert payload["generation_id"] == "gen-1"
    assert payload["request_json"]["still_generation"]["prompt"] == "panel prompt"
    assert (
        payload["request_json"]["still_generation"]["source_id"]
        == "comic-panel-render:panel-1:3:remote_worker"
    )
    assert payload["request_json"]["comic"] == {
        "scene_panel_id": "panel-1",
        "render_asset_id": "asset-1",
        "character_version_id": "charver_kaede_ren_still_v1",
    }


def test_build_comic_remote_worker_payload_includes_callback_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-callback-secret")

    payload = build_comic_remote_worker_payload(
        {
            "id": "comic-job-2",
            "generation_id": "gen-2",
            "target_tool": "comic_panel_still",
            "executor_mode": "remote_worker",
            "executor_key": "default",
            "request_json": "{}",
        },
        {
            "id": "gen-2",
            "prompt": "panel prompt",
            "negative_prompt": "bad anatomy",
            "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
            "loras": "[]",
            "steps": 34,
            "cfg": 5.5,
            "width": 832,
            "height": 1216,
            "sampler": "euler_ancestral",
            "scheduler": "normal",
            "clip_skip": 2,
            "source_id": "comic-panel-render:panel-1:3:remote_worker",
        },
        {
            "id": "asset-2",
            "scene_panel_id": "panel-1",
        },
        {
            "character_version_id": "charver_kaede_ren_still_v1",
        },
    )

    assert (
        payload["callback_url"]
        == "http://127.0.0.1:8000/api/v1/comic/render-jobs/comic-job-2/callback"
    )
    assert payload["callback_token"] == "comic-callback-secret"


@pytest.mark.parametrize(
    "public_api_base_url",
    [
        "",
        "not-a-url",
        "http://",
    ],
)
def test_build_comic_remote_worker_payload_fails_for_invalid_callback_base_url(
    monkeypatch: pytest.MonkeyPatch,
    public_api_base_url: str,
) -> None:
    from app.config import settings
    from app.services.comic_render_dispatch_service import ComicRenderDispatchError

    monkeypatch.setattr(settings, "PUBLIC_API_BASE_URL", public_api_base_url)

    with pytest.raises(
        ComicRenderDispatchError,
        match="PUBLIC_API_BASE_URL",
    ):
        build_comic_remote_worker_payload(
            {
                "id": "comic-job-invalid-callback",
                "generation_id": "gen-2",
                "target_tool": "comic_panel_still",
                "executor_mode": "remote_worker",
                "executor_key": "default",
                "request_json": "{}",
            },
            {
                "id": "gen-2",
                "prompt": "panel prompt",
                "negative_prompt": "bad anatomy",
                "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                "loras": "[]",
                "steps": 34,
                "cfg": 5.5,
                "width": 832,
                "height": 1216,
                "sampler": "euler_ancestral",
                "scheduler": "normal",
                "clip_skip": 2,
                "source_id": "comic-panel-render:panel-1:3:remote_worker",
            },
            {
                "id": "asset-2",
                "scene_panel_id": "panel-1",
            },
            {
                "character_version_id": "charver_kaede_ren_still_v1",
            },
        )
