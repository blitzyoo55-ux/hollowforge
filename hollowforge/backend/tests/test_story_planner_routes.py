from __future__ import annotations

import json

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.routes import marketing as marketing_routes
from app.services.story_planner_service import StoryPlannerValidationError

pytestmark = pytest.mark.asyncio


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(marketing_routes.router)
    return app


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tools/story-planner/catalog",
        "/api/tools/story-planner/catalog",
    ],
)
async def test_story_planner_catalog_route_returns_catalog_sections(path: str) -> None:
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(path)

    assert response.status_code == 200
    body = response.json()
    assert body["characters"]
    assert body["locations"]
    assert body["policy_packs"]
    adult_pack = next(pack for pack in body["policy_packs"] if pack["id"] == "canon_adult_nsfw_v1")
    assert adult_pack["prompt_provider_profile_id"] == "adult_openrouter_grok"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tools/story-planner/plan",
        "/api/tools/story-planner/plan",
    ],
)
async def test_story_planner_plan_route_returns_four_shot_preview(path: str) -> None:
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            path,
            json={
                "story_prompt": (
                    "Hana Seo compares notes with a quiet messenger in the "
                    "Moonlit Bathhouse corridor after closing."
                ),
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
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["policy_pack_id"] == "canon_adult_nsfw_v1"
    assert body["anchor_render"]["policy_pack_id"] == "canon_adult_nsfw_v1"
    assert body["anchor_render"]["checkpoint"] == "waiIllustriousSDXL_v140.safetensors"
    assert body["anchor_render"]["workflow_lane"] == "sdxl_illustrious"
    assert body["anchor_render"]["negative_prompt"] == (
        "minors, age ambiguity, non-consensual framing"
    )
    assert body["anchor_render"]["preserve_blank_negative_prompt"] is False
    assert body["location"]["id"] == "moonlit_bathhouse"
    assert "matched" in body["location"]["match_note"].lower()
    assert body["resolved_cast"][0]["source_type"] == "registry"
    assert body["resolved_cast"][0]["character_id"] == "hana_seo"
    assert body["resolved_cast"][0]["character_name"] == "Hana Seo"
    assert body["resolved_cast"][1]["source_type"] == "freeform"
    assert body["resolved_cast"][1]["character_id"] is None
    assert body["resolved_cast"][1]["character_name"] is None
    assert (
        body["resolved_cast"][1]["freeform_description"]
        == "quiet messenger in a dark coat"
    )
    assert body["episode_brief"]["premise"]
    assert len(body["shots"]) == 4
    assert body["recommended_anchor_shot_no"] == 2
    assert body["recommended_anchor_reason"]
    assert len(body["recommended_anchor_reason"]) <= 240


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tools/story-planner/plan",
        "/api/tools/story-planner/plan",
    ],
)
async def test_story_planner_plan_route_preserves_unresolved_registry_semantics(
    path: str,
) -> None:
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            path,
            json={
                "story_prompt": "An unknown consultant arrives with no clear setting cues.",
                "lane": "adult_nsfw",
                "cast": [
                    {
                        "role": "lead",
                        "source_type": "registry",
                        "character_id": "unknown_consultant",
                    }
                ],
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["policy_pack_id"] == "canon_adult_nsfw_v1"
    assert "fallback" in body["location"]["match_note"].lower()
    assert body["resolved_cast"][0]["character_id"] == "unknown_consultant"
    assert body["resolved_cast"][0]["character_name"] is None
    assert "not found" in body["resolved_cast"][0]["resolution_note"].lower()


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tools/story-planner/plan",
        "/api/tools/story-planner/plan",
    ],
)
async def test_story_planner_plan_route_rejects_invalid_location_lock_with_422(
    path: str,
) -> None:
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            path,
            json={
                "story_prompt": (
                    "Hana Seo compares notes with a quiet messenger in the "
                    "Moonlit Bathhouse corridor after closing."
                ),
                "lane": "adult_nsfw",
                "location_id": "not_a_real_location",
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
            },
        )

    assert response.status_code == 422
    assert "location_id" in json.dumps(response.json()["detail"])


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tools/story-planner/plan",
        "/api/tools/story-planner/plan",
    ],
)
async def test_story_planner_plan_route_maps_planner_validation_errors_to_422(
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_planner_validation_error(_payload):  # type: ignore[no-untyped-def]
        raise StoryPlannerValidationError("planner input is invalid")

    monkeypatch.setattr(marketing_routes, "plan_story_episode", _raise_planner_validation_error)
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            path,
            json={
                "story_prompt": "Hana Seo compares notes with a quiet messenger.",
                "lane": "adult_nsfw",
                "cast": [
                    {
                        "role": "lead",
                        "source_type": "registry",
                        "character_id": "hana_seo",
                    }
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "planner input is invalid"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tools/story-planner/plan",
        "/api/tools/story-planner/plan",
    ],
)
async def test_story_planner_plan_route_does_not_hide_unrelated_value_errors(
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_value_error(_payload):  # type: ignore[no-untyped-def]
        raise ValueError("unexpected planner failure")

    monkeypatch.setattr(marketing_routes, "plan_story_episode", _raise_value_error)
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            path,
            json={
                "story_prompt": "Hana Seo compares notes with a quiet messenger.",
                "lane": "adult_nsfw",
                "cast": [
                    {
                        "role": "lead",
                        "source_type": "registry",
                        "character_id": "hana_seo",
                    }
                ],
            },
        )

    assert response.status_code == 500


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/tools/story-planner/plan",
        "/api/tools/story-planner/plan",
    ],
)
async def test_story_planner_plan_route_supports_prompt_only_mode(path: str) -> None:
    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            path,
            json={
                "story_prompt": (
                    "Hana Seo meets a quiet messenger in the Moonlit Bathhouse "
                    "corridor after closing."
                ),
                "lane": "adult_nsfw",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["resolved_cast"][0]["source_type"] == "freeform"
    assert "Hana Seo" in body["resolved_cast"][0]["freeform_description"]
    assert body["resolved_cast"][1]["source_type"] == "freeform"
    assert "messenger" in body["resolved_cast"][1]["freeform_description"].lower()
