from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import UUID

import pytest

from app.db import init_db
from app.models import ProductionVerificationRunCreate
from app.services import production_verification_repository as repository
from app.services.production_verification_repository import (
    create_production_verification_run,
    get_production_verification_summary,
)


@pytest.mark.asyncio
async def test_list_summary_returns_latest_smoke_only_latest_suite_and_recent_runs(
    temp_db, monkeypatch
) -> None:
    await init_db()

    monkeypatch.setattr(repository, "_now_iso", lambda: "2026-04-19T00:00:00+00:00")
    uuid_values = iter(
        [
            UUID("00000000-0000-0000-0000-000000000010"),
            UUID("00000000-0000-0000-0000-000000000003"),
            UUID("00000000-0000-0000-0000-000000000002"),
        ]
    )
    monkeypatch.setattr(repository.uuid, "uuid4", lambda: next(uuid_values))

    await create_production_verification_run(
        ProductionVerificationRunCreate(
            run_mode="suite",
            status="completed",
            overall_success=True,
            base_url="http://127.0.0.1:8014",
            total_duration_sec=2.4,
            started_at="2026-04-19T00:00:00+00:00",
            finished_at="2026-04-19T00:00:00+00:00",
            stage_status={
                "suite": {
                    "status": "passed",
                    "duration_sec": 2.4,
                    "error_summary": None,
                }
            },
        )
    )
    await create_production_verification_run(
        ProductionVerificationRunCreate(
            run_mode="smoke_only",
            status="completed",
            overall_success=True,
            base_url="http://127.0.0.1:8014",
            total_duration_sec=1.2,
            started_at="2026-04-19T00:00:00+00:00",
            finished_at="2026-04-19T00:00:05+00:00",
            stage_status={
                "smoke": {
                    "status": "passed",
                    "duration_sec": 1.2,
                    "error_summary": None,
                }
            },
        )
    )
    await create_production_verification_run(
        ProductionVerificationRunCreate(
            run_mode="suite",
            status="failed",
            overall_success=False,
            failure_stage="ui",
            error_summary="Suite stopped on ui stage.",
            base_url="http://127.0.0.1:8014",
            total_duration_sec=2.0,
            started_at="2026-04-19T00:00:00+00:00",
            finished_at="2026-04-19T00:00:10+00:00",
            stage_status={
                "smoke": {
                    "status": "passed",
                    "duration_sec": 0.2,
                    "error_summary": None,
                },
                "ui": {
                    "status": "failed",
                    "duration_sec": 1.8,
                    "error_summary": "Suite stopped on ui stage.",
                },
            },
        )
    )

    real_get_db = repository.get_db
    call_count = 0

    @asynccontextmanager
    async def counting_get_db():
        nonlocal call_count
        call_count += 1
        async with real_get_db() as db:
            yield db

    monkeypatch.setattr(repository, "get_db", counting_get_db)

    summary = await get_production_verification_summary(limit=5)
    assert call_count == 1
    assert summary.latest_smoke_only is not None
    assert summary.latest_smoke_only.id == "00000000-0000-0000-0000-000000000003"
    assert summary.latest_suite is not None
    assert summary.latest_suite.id == "00000000-0000-0000-0000-000000000002"
    assert [run.id for run in summary.recent_runs] == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000010",
    ]


@pytest.mark.asyncio
async def test_create_production_verification_run_round_trips_stage_status_json(
    temp_db, monkeypatch
) -> None:
    await init_db()

    monkeypatch.setattr(repository, "_now_iso", lambda: "2026-04-19T00:00:00+00:00")
    monkeypatch.setattr(
        repository.uuid,
        "uuid4",
        lambda: UUID("00000000-0000-0000-0000-000000000010"),
    )

    created = await create_production_verification_run(
        ProductionVerificationRunCreate(
            run_mode="ui_only",
            status="completed",
            overall_success=True,
            base_url="http://127.0.0.1:8014",
            total_duration_sec=1.2,
            started_at="2026-04-19T00:00:00+00:00",
            finished_at="2026-04-19T00:00:01+00:00",
            stage_status={
                "ui": {
                    "status": "passed",
                    "duration_sec": 1.2,
                    "error_summary": None,
                }
            },
        )
    )

    assert created.stage_status["ui"].status == "passed"
    assert created.stage_status["ui"].duration_sec == 1.2

    summary = await get_production_verification_summary(limit=5)
    assert summary.recent_runs[0].stage_status["ui"].status == "passed"
    assert summary.recent_runs[0].stage_status["ui"].duration_sec == 1.2
    assert summary.recent_runs[0].stage_status["ui"].error_summary is None


@pytest.mark.asyncio
async def test_create_production_verification_run_uses_explicit_id_when_provided(
    temp_db, monkeypatch
) -> None:
    await init_db()

    monkeypatch.setattr(repository, "_now_iso", lambda: "2026-04-19T00:00:00+00:00")
    monkeypatch.setattr(
        repository.uuid,
        "uuid4",
        lambda: UUID("00000000-0000-0000-0000-000000000999"),
    )

    created = await create_production_verification_run(
        ProductionVerificationRunCreate(
            id="prod-run-explicit-1",
            run_mode="suite",
            status="completed",
            overall_success=True,
            base_url="http://127.0.0.1:8014",
            total_duration_sec=2.1,
            started_at="2026-04-19T00:00:00+00:00",
            finished_at="2026-04-19T00:00:02+00:00",
            stage_status={
                "smoke": {
                    "status": "passed",
                    "duration_sec": 2.1,
                    "error_summary": None,
                }
            },
        )
    )

    assert created.id == "prod-run-explicit-1"

    summary = await get_production_verification_summary(limit=5)
    assert summary.recent_runs[0].id == "prod-run-explicit-1"
