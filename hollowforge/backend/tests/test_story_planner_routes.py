from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.routes import marketing as marketing_routes

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
    assert body["episode_brief"]["premise"]
    assert len(body["shots"]) == 4
