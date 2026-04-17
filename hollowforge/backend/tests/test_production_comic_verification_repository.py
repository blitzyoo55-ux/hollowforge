from __future__ import annotations

from uuid import UUID

import pytest

from app.db import init_db
from app.models import ComicVerificationRunCreate
from app.services import production_comic_verification_repository as repository
from app.services.production_comic_verification_repository import (
    create_comic_verification_run,
    get_comic_verification_summary,
)


@pytest.mark.asyncio
async def test_list_summary_returns_latest_preflight_latest_suite_and_recent_runs(
    temp_db, monkeypatch
) -> None:
    await init_db()

    monkeypatch.setattr(repository, "_now_iso", lambda: "2026-04-17T00:00:00+00:00")
    uuid_values = iter(
        [
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000003"),
            UUID("00000000-0000-0000-0000-000000000002"),
        ]
    )
    monkeypatch.setattr(repository.uuid, "uuid4", lambda: next(uuid_values))

    await create_comic_verification_run(
        ComicVerificationRunCreate(
            run_mode="suite",
            status="completed",
            overall_success=True,
            base_url="http://127.0.0.1:8000",
            total_duration_sec=2.4,
            started_at="2026-04-17T00:00:00+00:00",
            finished_at="2026-04-17T00:00:00+00:00",
            stage_status={
                "suite": {
                    "status": "passed",
                    "duration_sec": 2.4,
                    "error_summary": None,
                }
            },
        )
    )
    await create_comic_verification_run(
        ComicVerificationRunCreate(
            run_mode="preflight",
            status="completed",
            overall_success=True,
            base_url="http://127.0.0.1:8000",
            total_duration_sec=1.2,
            started_at="2026-04-17T00:00:00+00:00",
            finished_at="2026-04-17T00:00:10+00:00",
            stage_status={
                "preflight": {
                    "status": "passed",
                    "duration_sec": 1.2,
                    "error_summary": None,
                }
            },
        )
    )
    await create_comic_verification_run(
        ComicVerificationRunCreate(
            run_mode="suite",
            status="failed",
            overall_success=False,
            failure_stage="suite",
            error_summary="Suite stopped on stage 2.",
            base_url="http://127.0.0.1:8000",
            total_duration_sec=2.0,
            started_at="2026-04-17T00:00:00+00:00",
            finished_at="2026-04-17T00:00:00+00:00",
            stage_status={
                "suite": {
                    "status": "failed",
                    "duration_sec": 2.0,
                    "error_summary": "Suite stopped on stage 2.",
                }
            },
        )
    )
    summary = await get_comic_verification_summary(limit=5)
    assert summary.latest_preflight is not None
    assert summary.latest_preflight.id == "00000000-0000-0000-0000-000000000003"
    assert summary.latest_suite is not None
    assert summary.latest_suite.id == "00000000-0000-0000-0000-000000000002"
    assert [run.id for run in summary.recent_runs] == [
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000001",
    ]


@pytest.mark.asyncio
async def test_create_comic_verification_run_round_trips_stage_status_json(
    temp_db, monkeypatch
) -> None:
    await init_db()

    monkeypatch.setattr(repository, "_now_iso", lambda: "2026-04-17T00:00:00+00:00")
    monkeypatch.setattr(
        repository.uuid,
        "uuid4",
        lambda: UUID("00000000-0000-0000-0000-000000000010"),
    )

    created = await create_comic_verification_run(
        ComicVerificationRunCreate(
            run_mode="preflight",
            status="completed",
            overall_success=True,
            base_url="http://127.0.0.1:8000",
            total_duration_sec=1.2,
            started_at="2026-04-17T00:00:00+00:00",
            finished_at="2026-04-17T00:00:01+00:00",
            stage_status={
                "preflight": {
                    "status": "passed",
                    "duration_sec": 1.2,
                    "error_summary": None,
                }
            },
        )
    )

    assert created.stage_status["preflight"].status == "passed"
    assert created.stage_status["preflight"].duration_sec == 1.2

    summary = await get_comic_verification_summary(limit=5)
    assert summary.recent_runs[0].stage_status["preflight"].status == "passed"
    assert summary.recent_runs[0].stage_status["preflight"].duration_sec == 1.2
    assert summary.recent_runs[0].stage_status["preflight"].error_summary is None
