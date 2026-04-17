from __future__ import annotations

import pytest

from app.db import init_db
from app.models import ComicVerificationRunCreate
from app.services.production_comic_verification_repository import (
    create_comic_verification_run,
    get_comic_verification_summary,
)


@pytest.mark.asyncio
async def test_list_summary_returns_latest_preflight_latest_suite_and_recent_runs(temp_db) -> None:
    await init_db()
    await create_comic_verification_run(
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
    summary = await get_comic_verification_summary(limit=5)
    assert summary.latest_preflight is not None
    assert summary.latest_suite is None
    assert len(summary.recent_runs) == 1
