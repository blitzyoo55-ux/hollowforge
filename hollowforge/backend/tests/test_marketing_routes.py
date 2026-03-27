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

    async def queue_generation(self, generation):  # type: ignore[no-untyped-def]
        self.generation_requests.append(generation)
        return _build_generation_response(
            f"queued-{len(self.generation_requests)}",
            prompt=generation.prompt,
        )


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

