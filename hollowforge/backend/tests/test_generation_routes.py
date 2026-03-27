from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.models import GenerationResponse
from app.routes.generations import router as generations_router

pytestmark = pytest.mark.asyncio


def _now() -> str:
    return datetime(2026, 3, 27, 0, 0, tzinfo=timezone.utc).isoformat()


def _build_generation_response(
    generation_id: str,
    *,
    prompt: str = "portrait prompt",
    checkpoint: str = "checkpoint.safetensors",
    seed: int = 123,
    status: str = "queued",
) -> GenerationResponse:
    return GenerationResponse(
        id=generation_id,
        prompt=prompt,
        checkpoint=checkpoint,
        loras=[],
        seed=seed,
        steps=28,
        cfg=7.0,
        width=832,
        height=1216,
        sampler="euler",
        scheduler="normal",
        status=status,
        created_at=_now(),
    )


class _StubGenerationService:
    def __init__(self) -> None:
        self.generation_requests = []
        self.batch_requests = []

    async def queue_generation(self, generation):  # type: ignore[no-untyped-def]
        self.generation_requests.append(generation)
        return _build_generation_response(
            "gen-single-1",
            prompt=generation.prompt,
            checkpoint=generation.checkpoint,
            seed=generation.seed or 123,
        )

    async def queue_generation_batch(self, generation, count: int, seed_increment: int):  # type: ignore[no-untyped-def]
        self.batch_requests.append((generation, count, seed_increment))
        base_seed = 500
        queued = [
            _build_generation_response(
                f"gen-batch-{index}",
                prompt=generation.prompt,
                checkpoint=generation.checkpoint,
                seed=base_seed + ((index - 1) * seed_increment),
            )
            for index in range(1, count + 1)
        ]
        return base_seed, queued


def _build_app(service: _StubGenerationService) -> FastAPI:
    app = FastAPI()
    app.state.generation_service = service
    app.include_router(generations_router)
    return app


def _insert_generation_row(
    db_path: Path,
    *,
    generation_id: str,
    status: str,
    created_at: str,
    generation_time_sec: float | None = None,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO generations (
                id,
                prompt,
                checkpoint,
                loras,
                tags,
                seed,
                steps,
                cfg,
                width,
                height,
                sampler,
                scheduler,
                status,
                image_path,
                notes,
                created_at,
                completed_at,
                generation_time_sec
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                generation_id,
                f"prompt {generation_id}",
                "checkpoint.safetensors",
                json.dumps([]),
                json.dumps(["smoke"]),
                42,
                28,
                7.0,
                832,
                1216,
                "euler",
                "normal",
                status,
                f"images/{generation_id}.png",
                f"notes {generation_id}",
                created_at,
                created_at if status == "completed" else None,
                generation_time_sec,
            ),
        )
        conn.commit()


def _clear_seed_rows(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM publish_jobs")
        conn.execute("DELETE FROM generations")
        conn.commit()


async def test_create_generation_route_queues_request_via_service() -> None:
    service = _StubGenerationService()
    app = _build_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/generations",
            json={
                "prompt": "smoke portrait",
                "checkpoint": "waiIllustriousSDXL_v160.safetensors",
                "seed": 101,
                "steps": 30,
                "cfg": 6.0,
                "width": 832,
                "height": 1216,
                "sampler": "euler_a",
                "scheduler": "normal",
            },
        )

    assert response.status_code == 201
    assert service.generation_requests[0].prompt == "smoke portrait"
    assert service.generation_requests[0].checkpoint == "waiIllustriousSDXL_v160.safetensors"
    assert response.json()["id"] == "gen-single-1"


async def test_create_generation_batch_route_returns_service_batch_payload() -> None:
    service = _StubGenerationService()
    app = _build_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/generations/batch",
            json={
                "generation": {
                    "prompt": "batch portrait",
                    "checkpoint": "prefectIllustriousXL_v70.safetensors",
                    "seed": 500,
                    "steps": 28,
                    "cfg": 5.4,
                    "width": 832,
                    "height": 1216,
                    "sampler": "euler",
                    "scheduler": "normal",
                },
                "count": 3,
                "seed_increment": 2,
            },
        )

    assert response.status_code == 201
    assert service.batch_requests[0][1:] == (3, 2)
    payload = response.json()
    assert payload["count"] == 3
    assert payload["base_seed"] == 500
    assert [row["seed"] for row in payload["generations"]] == [500, 502, 504]


async def test_queue_summary_route_reports_running_and_queued_items(temp_db: Path) -> None:
    service = _StubGenerationService()
    app = _build_app(service)

    _clear_seed_rows(temp_db)
    _insert_generation_row(
        temp_db,
        generation_id="gen-completed-1",
        status="completed",
        created_at="2026-03-27T00:00:00+00:00",
        generation_time_sec=42.0,
    )
    _insert_generation_row(
        temp_db,
        generation_id="gen-running-1",
        status="running",
        created_at="2026-03-27T00:10:00+00:00",
    )
    _insert_generation_row(
        temp_db,
        generation_id="gen-queued-1",
        status="queued",
        created_at="2026-03-27T00:20:00+00:00",
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/generations/queue/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_running"] == 1
    assert payload["total_queued"] == 1
    assert payload["avg_generation_sec"] == 42.0
    assert [item["id"] for item in payload["queue_items"]] == ["gen-running-1", "gen-queued-1"]
