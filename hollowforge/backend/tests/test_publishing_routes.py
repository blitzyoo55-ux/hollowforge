from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.config import settings
from app.routes.publishing import router as publishing_router

pytestmark = pytest.mark.asyncio


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(publishing_router)
    return app


def _now() -> str:
    return datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc).isoformat()


def _insert_caption_variant(
    db_path: Path,
    *,
    caption_id: str,
    generation_id: str,
    channel: str = "social_short",
    platform: str = "pixiv",
    approved: int = 0,
) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO caption_variants (
                id,
                generation_id,
                channel,
                platform,
                provider,
                model,
                prompt_version,
                tone,
                story,
                hashtags,
                approved,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                caption_id,
                generation_id,
                channel,
                platform,
                settings.MARKETING_PROVIDER_NAME,
                settings.MARKETING_MODEL,
                settings.MARKETING_PROMPT_VERSION,
                "teaser",
                f"story for {caption_id}",
                "#hf",
                approved,
                _now(),
                _now(),
            ),
        )
        conn.commit()


async def test_publishing_readiness_returns_draft_only_without_openrouter_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/publishing/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "caption_generation_ready": False,
        "draft_publish_ready": True,
        "degraded_mode": "draft_only",
        "provider": settings.MARKETING_PROVIDER_NAME,
        "model": settings.MARKETING_MODEL,
        "missing_requirements": ["OPENROUTER_API_KEY"],
        "notes": [],
    }


async def test_publishing_readiness_returns_full_when_openrouter_key_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-openrouter-key")

    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/publishing/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "caption_generation_ready": True,
        "draft_publish_ready": True,
        "degraded_mode": "full",
        "provider": settings.MARKETING_PROVIDER_NAME,
        "model": settings.MARKETING_MODEL,
        "missing_requirements": [],
        "notes": [],
    }


async def test_generate_caption_returns_503_when_openrouter_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    async def fake_generate_caption_from_image_bytes(*args, **kwargs):
        return {"story": "should not be used", "hashtags": "#ok"}

    monkeypatch.setattr(
        "app.routes.publishing.generate_caption_from_image_bytes",
        fake_generate_caption_from_image_bytes,
    )

    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/publishing/generations/gen-ready-1/captions/generate",
            json={
                "platform": "twitter",
                "tone": "teaser",
                "channel": "social_short",
                "approved": False,
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Caption generation unavailable: OPENROUTER_API_KEY is not configured"
    }


async def test_approve_caption_route_marks_only_selected_variant_as_approved(
    temp_db: Path,
) -> None:
    _insert_caption_variant(temp_db, caption_id="caption-a", generation_id="gen-ready-2", approved=1)
    _insert_caption_variant(temp_db, caption_id="caption-b", generation_id="gen-ready-2", approved=0)

    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/api/v1/publishing/captions/caption-b/approve")

    assert response.status_code == 200
    assert response.json()["id"] == "caption-b"
    assert response.json()["approved"] is True

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            "SELECT id, approved FROM caption_variants WHERE generation_id = ? ORDER BY id",
            ("gen-ready-2",),
        ).fetchall()

    assert rows == [("caption-a", 0), ("caption-b", 1)]


async def test_create_draft_publish_job_keeps_linked_caption_variant_id(
    temp_db: Path,
) -> None:
    _insert_caption_variant(temp_db, caption_id="caption-pixiv-1", generation_id="gen-ready-2")

    app = _build_app()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/api/v1/publishing/posts",
            json={
                "generation_id": "gen-ready-2",
                "caption_variant_id": "caption-pixiv-1",
                "platform": "pixiv",
                "status": "draft",
            },
        )

    assert response.status_code == 201
    assert response.json()["generation_id"] == "gen-ready-2"
    assert response.json()["caption_variant_id"] == "caption-pixiv-1"
    assert response.json()["platform"] == "pixiv"
    assert response.json()["status"] == "draft"
