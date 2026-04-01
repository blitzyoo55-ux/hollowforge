from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.config import settings
from app.db import get_db
from app.models import PublishJobCreate
from app.routes.publishing import (
    create_publish_job,
    list_generation_publish_jobs,
    list_ready_publish_items as list_ready_publish_items_route,
    router as publishing_router,
)

pytestmark = pytest.mark.asyncio


async def test_ready_publish_items_can_be_filtered_to_selected_generation_ids():
    from app.services.publishing_service import list_ready_publish_items

    items = await list_ready_publish_items(selected_generation_ids=["gen-ready-2"])

    assert [item.generation_id for item in items] == ["gen-ready-2"]


async def test_existing_draft_publish_job_is_reused_instead_of_duplicated():
    from app.services.publishing_service import create_or_reuse_draft_publish_job

    first_job = await create_or_reuse_draft_publish_job(
        generation_id="gen-ready-1",
        platform="twitter",
    )
    second_job = await create_or_reuse_draft_publish_job(
        generation_id="gen-ready-1",
        platform="twitter",
    )

    assert second_job.id == first_job.id
    assert second_job.status == "draft"

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) AS count
            FROM publish_jobs
            WHERE generation_id = ? AND platform = ?
            """,
            ("gen-ready-1", "twitter"),
        )
        row = await cursor.fetchone()

    assert row["count"] == 1


async def test_existing_draft_reuse_ignores_new_caption_variant_and_notes():
    from app.services.publishing_service import create_or_reuse_draft_publish_job

    job = await create_or_reuse_draft_publish_job(
        generation_id="gen-ready-1",
        platform="twitter",
        caption_variant_id="caption-new",
        notes="should be ignored",
    )

    assert job.id == "publish-job-draft-1"
    assert job.caption_variant_id is None
    assert job.notes == "existing draft job"


async def test_route_draft_publish_job_creation_is_idempotent_for_same_pair():
    first_job = await create_publish_job(
        PublishJobCreate(
            generation_id="gen-ready-1",
            platform="twitter",
            status="draft",
        )
    )
    second_job = await create_publish_job(
        PublishJobCreate(
            generation_id="gen-ready-1",
            platform="twitter",
            status="draft",
        )
    )

    assert second_job.id == first_job.id
    assert second_job.status == "draft"


async def test_draft_publish_job_creation_still_succeeds_without_openrouter_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")

    job = await create_publish_job(
        PublishJobCreate(
            generation_id="gen-ready-2",
            platform="twitter",
            status="draft",
        )
    )

    assert job.generation_id == "gen-ready-2"
    assert job.status == "draft"


async def test_generation_publish_jobs_route_lists_jobs_for_requested_generation():
    jobs = await list_generation_publish_jobs("gen-ready-1")

    assert [job.id for job in jobs] == ["publish-job-draft-1"]


async def test_ready_publish_items_route_accepts_repeated_generation_id_filters():
    items = await list_ready_publish_items_route(
        limit=100,
        generation_id=["gen-ready-2"],
    )

    assert [item.generation_id for item in items] == ["gen-ready-2"]


async def test_ready_publish_items_http_route_parses_repeated_generation_id_filters():
    app = FastAPI()
    app.include_router(publishing_router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/api/v1/publishing/ready-items",
            params=[
                ("generation_id", "gen-ready-2"),
                ("generation_id", "gen-ready-1"),
            ],
        )

    assert response.status_code == 200
    assert [item["generation_id"] for item in response.json()] == [
        "gen-ready-1",
        "gen-ready-2",
    ]
