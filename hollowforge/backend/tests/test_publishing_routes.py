from __future__ import annotations

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
