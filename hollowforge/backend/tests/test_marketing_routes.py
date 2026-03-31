from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.models import (
    GenerationResponse,
    PromptBatchGenerateResponse,
    PromptBatchRowResponse,
    PromptFactoryBenchmarkResponse,
)
from app.routes import marketing as marketing_routes
from app.services import story_planner_service

pytestmark = pytest.mark.asyncio


def _now() -> str:
    return datetime(2026, 3, 27, 0, 0, tzinfo=timezone.utc).isoformat()


def _build_generation_response(generation_id: str, *, prompt: str) -> GenerationResponse:
    return GenerationResponse(
        id=generation_id,
        prompt=prompt,
        checkpoint="waiIllustriousSDXL_v160.safetensors",
        loras=[],
        seed=700,
        steps=28,
        cfg=7.0,
        width=832,
        height=1216,
        sampler="euler",
        scheduler="normal",
        status="queued",
        created_at=_now(),
    )


class _StubGenerationService:
    def __init__(self) -> None:
        self.generation_requests = []
        self.batch_requests = []

    async def queue_generation(self, generation):  # type: ignore[no-untyped-def]
        self.generation_requests.append(generation)
        return _build_generation_response(
            f"queued-{len(self.generation_requests)}",
            prompt=generation.prompt,
        )

    async def queue_generation_batch(  # type: ignore[no-untyped-def]
        self,
        generation,
        count: int,
        seed_increment: int,
    ):
        self.batch_requests.append((generation, count, seed_increment))
        base_seed = 700
        queued = [
            _build_generation_response(
                f"queued-batch-{len(self.batch_requests)}-{index + 1}",
                prompt=generation.prompt,
            )
            for index in range(count)
        ]
        return base_seed, queued


def _build_app(service: _StubGenerationService) -> FastAPI:
    app = FastAPI()
    app.state.generation_service = service
    app.include_router(marketing_routes.router)
    return app


def _insert_generation_row(db_path: Path, *, generation_id: str, image_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO generations (
                id,
                prompt,
                checkpoint,
                seed,
                image_path,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                generation_id,
                "caption prompt",
                "waiIllustriousSDXL_v160.safetensors",
                303,
                image_path,
                _now(),
            ),
        )
        conn.commit()


async def test_generate_caption_by_id_reads_nested_image_path(temp_db: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    nested_dir = temp_db.parent / "images" / "2026-03-27"
    nested_dir.mkdir(parents=True, exist_ok=True)
    image_path = nested_dir / "gen-caption-1.png"
    image_path.write_bytes(b"nested-image-bytes")
    _insert_generation_row(
        temp_db,
        generation_id="gen-caption-1",
        image_path="images/2026-03-27/gen-caption-1.png",
    )

    async def fake_generate_caption(image_bytes: bytes, mime_type: str, **_: object) -> dict[str, str]:
        assert image_bytes == b"nested-image-bytes"
        assert mime_type == "image/png"
        return {"story": "caption story", "hashtags": "#hf"}

    monkeypatch.setattr(marketing_routes, "generate_caption_from_image_bytes", fake_generate_caption)

    app = _build_app(_StubGenerationService())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/tools/generate-caption-by-id",
            json={"generation_id": "gen-caption-1"},
        )

    assert response.status_code == 200
    assert response.json() == {"story": "caption story", "hashtags": "#hf"}


async def test_prompt_factory_generate_and_queue_translates_rows_to_generation_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubGenerationService()

    async def fake_generate_prompt_batch(_payload):  # type: ignore[no-untyped-def]
        return PromptBatchGenerateResponse(
            provider="openrouter",
            model="x-ai/grok-4.1-fast",
            requested_count=1,
            generated_count=1,
            chunk_count=1,
            benchmark=PromptFactoryBenchmarkResponse(
                favorites_total=10,
                workflow_lane="sdxl_illustrious",
                prompt_dialect="tag_stack",
                top_checkpoints=["waiIllustriousSDXL_v160.safetensors"],
                top_loras=[],
                avg_lora_strength=0.45,
                cfg_values=[5.4],
                steps_values=[30],
                sampler="euler_a",
                scheduler="normal",
                clip_skip=2,
                width=832,
                height=1216,
                theme_keywords=["editorial"],
                material_cues=[],
                control_cues=[],
                camera_cues=[],
                environment_cues=[],
                exposure_cues=[],
                negative_prompt="bad anatomy",
            ),
            direction_pack=[],
            rows=[
                PromptBatchRowResponse(
                    set_no=1,
                    codename="alpha",
                    series="series_a",
                    checkpoint="waiIllustriousSDXL_v160.safetensors",
                    workflow_lane="sdxl_illustrious",
                    loras=[],
                    sampler="euler_a",
                    steps=30,
                    cfg=5.4,
                    clip_skip=2,
                    width=832,
                    height=1216,
                    positive_prompt="prompt alpha",
                    negative_prompt="bad anatomy",
                )
            ],
        )

    monkeypatch.setattr(marketing_routes, "generate_prompt_batch", fake_generate_prompt_batch)

    app = _build_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/tools/prompt-factory/generate-and-queue",
            json={
                "concept_brief": "editorial portrait test",
                "count": 1,
            },
        )

    assert response.status_code == 200
    assert len(service.generation_requests) == 1
    queued = service.generation_requests[0]
    assert queued.prompt == "prompt alpha"
    assert queued.tags == ["prompt_batch_001", "series_a", "alpha"]
    assert queued.notes == "Prompt factory batch row 1: alpha"


@pytest.mark.parametrize("base_path", ["/api/v1", "/api"])
async def test_story_planner_approve_and_generate_queues_two_candidates_per_shot(
    base_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubGenerationService()
    app = _build_app(service)

    plan_payload = {
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
    }

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        preview_response = await client.post(
            f"{base_path}/tools/story-planner/plan",
            json=plan_payload,
        )
        assert preview_response.status_code == 200
        approved_plan = preview_response.json()
        assert approved_plan["policy_pack_id"] == "canon_adult_nsfw_v1"
        assert approved_plan["anchor_render"]["policy_pack_id"] == "canon_adult_nsfw_v1"
        assert approved_plan["anchor_render"]["checkpoint"] == "waiIllustriousSDXL_v140.safetensors"
        assert approved_plan["approval_token"]
        assert approved_plan["resolved_cast"][0]["canonical_anchor"]
        assert approved_plan["resolved_cast"][0]["anti_drift"]
        assert approved_plan["resolved_cast"][0]["wardrobe_notes"]
        assert approved_plan["resolved_cast"][0]["personality_notes"]
        assert approved_plan["location"]["visual_rules"]
        assert approved_plan["location"]["restricted_elements"]

        def fail_catalog_reload():  # type: ignore[no-untyped-def]
            raise AssertionError("queue path should not reload story planner catalog")

        monkeypatch.setattr(
            story_planner_service,
            "load_story_planner_catalog",
            fail_catalog_reload,
        )

        response = await client.post(
            f"{base_path}/tools/story-planner/generate-anchors",
            json={
                "approved_plan": approved_plan,
                "candidate_count": 2,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["lane"] == "adult_nsfw"
    assert payload["requested_shot_count"] == 4
    assert payload["queued_generation_count"] == 8
    assert [shot["shot_no"] for shot in payload["queued_shots"]] == [1, 2, 3, 4]
    assert all(len(shot["generation_ids"]) == 2 for shot in payload["queued_shots"])
    assert len(payload["queued_generations"]) == 8

    assert len(service.batch_requests) == 4
    first_request, count, seed_increment = service.batch_requests[0]
    assert count == 2
    assert seed_increment == 1
    assert first_request.checkpoint == "waiIllustriousSDXL_v140.safetensors"
    assert first_request.workflow_lane == "sdxl_illustrious"
    assert first_request.preserve_blank_negative_prompt is False
    assert "story_planner_anchor" in first_request.prompt
    assert "policy_pack: canon_adult_nsfw_v1" in first_request.prompt
    assert "Moonlit Bathhouse" in first_request.prompt
    assert "Hana Seo" in first_request.prompt
    assert "canonical_anchor" in first_request.prompt
    assert "anti_drift" in first_request.prompt
    assert "wardrobe_notes" in first_request.prompt
    assert "personality_notes" in first_request.prompt
    assert "location_visual_rules" in first_request.prompt
    assert (
        "Preserve premium spa materials such as stone, wood, steam-softened light, and muted reflective surfaces."
        in first_request.prompt
    )
    assert "location_restricted_elements" in first_request.prompt
    assert "shot_01" in first_request.notes
    assert "story_planner_anchor" in first_request.notes
    assert "policy_pack=canon_adult_nsfw_v1" in first_request.notes
    assert first_request.tags is not None
    assert "story_planner_anchor" in first_request.tags
    assert "policy_pack:canon_adult_nsfw_v1" in first_request.tags
    assert "shot_01" in first_request.tags
    assert first_request.source_id is not None
    assert first_request.source_id.startswith("story_planner_anchor:")
    assert ":shot_01" in first_request.source_id


@pytest.mark.parametrize("base_path", ["/api/v1", "/api"])
async def test_story_planner_approve_and_generate_rejects_tampered_approval_token(
    base_path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _StubGenerationService()
    app = _build_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        preview_response = await client.post(
            f"{base_path}/tools/story-planner/plan",
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
        assert preview_response.status_code == 200
        approved_plan = preview_response.json()
        approved_plan["story_prompt"] = (
            "Hana Seo compares notes in a different corridor after closing."
        )

        def fail_catalog_reload():  # type: ignore[no-untyped-def]
            raise AssertionError("queue path should not reload story planner catalog")

        monkeypatch.setattr(
            story_planner_service,
            "load_story_planner_catalog",
            fail_catalog_reload,
        )
        response = await client.post(
            f"{base_path}/tools/story-planner/generate-anchors",
            json={
                "approved_plan": approved_plan,
                "candidate_count": 2,
            },
        )

    assert response.status_code == 400
    assert "approval_token" in response.text.lower()
    assert service.batch_requests == []


@pytest.mark.parametrize("base_path", ["/api/v1", "/api"])
async def test_story_planner_approve_and_generate_preserves_blank_negative_prompt_for_unrestricted_lane(
    base_path: str,
) -> None:
    service = _StubGenerationService()
    app = _build_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        preview_response = await client.post(
            f"{base_path}/tools/story-planner/plan",
            json={
                "story_prompt": "Hana Seo crosses the Moonlit Bathhouse lobby before dawn.",
                "lane": "unrestricted",
                "cast": [
                    {
                        "role": "lead",
                        "source_type": "registry",
                        "character_id": "hana_seo",
                    }
                ],
            },
        )
        assert preview_response.status_code == 200

        response = await client.post(
            f"{base_path}/tools/story-planner/generate-anchors",
            json={
                "approved_plan": preview_response.json(),
                "candidate_count": 2,
            },
        )

    assert response.status_code == 200
    first_request, _, _ = service.batch_requests[0]
    assert first_request.negative_prompt is None
    assert first_request.preserve_blank_negative_prompt is True


@pytest.mark.parametrize("base_path", ["/api/v1", "/api"])
async def test_story_planner_approve_and_generate_rejects_malformed_shot_numbers(
    base_path: str,
) -> None:
    service = _StubGenerationService()
    app = _build_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        preview_response = await client.post(
            f"{base_path}/tools/story-planner/plan",
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
                    }
                ],
            },
        )
        assert preview_response.status_code == 200
        approved_plan = preview_response.json()
        approved_plan["shots"][1]["shot_no"] = 1

        response = await client.post(
            f"{base_path}/tools/story-planner/generate-anchors",
            json={
                "approved_plan": approved_plan,
                "candidate_count": 2,
            },
        )

    assert response.status_code == 422
    assert "canonical shot numbers" in response.text
