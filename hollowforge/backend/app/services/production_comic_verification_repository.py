"""Repository helpers for comic verification run history."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from app.db import get_db
from app.models import (
    ComicVerificationRunCreate,
    ComicVerificationRunResponse,
    ComicVerificationStageStatusResponse,
    ComicVerificationSummaryResponse,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode_stage_status(
    stage_status: dict[str, ComicVerificationStageStatusResponse],
) -> dict[str, dict[str, Any]]:
    return {
        stage_name: stage_status_response.model_dump()
        for stage_name, stage_status_response in stage_status.items()
    }


def _decode_stage_status_json(
    value: Any,
) -> dict[str, ComicVerificationStageStatusResponse]:
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON object in comic_verification_runs.stage_status_json") from exc
    else:
        parsed = value
    if not isinstance(parsed, dict):
        raise ValueError("Invalid JSON object in comic_verification_runs.stage_status_json")
    return {
        str(stage_name): ComicVerificationStageStatusResponse.model_validate(stage_data)
        for stage_name, stage_data in parsed.items()
    }


def _run_response(row: dict[str, Any]) -> ComicVerificationRunResponse:
    payload = dict(row)
    payload["overall_success"] = bool(payload.get("overall_success"))
    payload["stage_status"] = _decode_stage_status_json(
        payload.pop("stage_status_json", None)
    )
    return ComicVerificationRunResponse.model_validate(payload)


async def create_comic_verification_run(
    payload: ComicVerificationRunCreate,
) -> ComicVerificationRunResponse:
    run_id = str(uuid.uuid4())
    now = _now_iso()
    stage_status_json = json.dumps(
        _encode_stage_status(payload.stage_status),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO comic_verification_runs (
                id, run_mode, status, overall_success, failure_stage,
                error_summary, base_url, total_duration_sec,
                started_at, finished_at, stage_status_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                payload.run_mode,
                payload.status,
                int(payload.overall_success),
                payload.failure_stage,
                payload.error_summary,
                payload.base_url,
                payload.total_duration_sec,
                payload.started_at,
                payload.finished_at,
                stage_status_json,
                now,
                now,
            ),
        )
        await db.commit()

    return ComicVerificationRunResponse(
        id=run_id,
        run_mode=payload.run_mode,
        status=payload.status,
        overall_success=payload.overall_success,
        failure_stage=payload.failure_stage,
        error_summary=payload.error_summary,
        base_url=payload.base_url,
        total_duration_sec=payload.total_duration_sec,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        stage_status=payload.stage_status,
        created_at=now,
        updated_at=now,
    )


async def _fetch_latest_run_for_mode(
    db,
    run_mode: str,
) -> ComicVerificationRunResponse | None:
    cursor = await db.execute(
        """
        SELECT
            id,
            run_mode,
            status,
            overall_success,
            failure_stage,
            error_summary,
            base_url,
            total_duration_sec,
            started_at,
            finished_at,
            stage_status_json,
            created_at,
            updated_at
        FROM comic_verification_runs
        WHERE run_mode = ?
        ORDER BY finished_at DESC, created_at DESC, id DESC
        LIMIT 1
        """,
        (run_mode,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return _run_response(cast(dict[str, Any], row))


async def _fetch_recent_runs(
    db,
    limit: int,
) -> list[ComicVerificationRunResponse]:
    cursor = await db.execute(
        """
        SELECT
            id,
            run_mode,
            status,
            overall_success,
            failure_stage,
            error_summary,
            base_url,
            total_duration_sec,
            started_at,
            finished_at,
            stage_status_json,
            created_at,
            updated_at
        FROM comic_verification_runs
        ORDER BY finished_at DESC, created_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = await cursor.fetchall()
    return [_run_response(cast(dict[str, Any], row)) for row in rows]


async def get_comic_verification_summary(
    limit: int = 10,
) -> ComicVerificationSummaryResponse:
    async with get_db() as db:
        await db.execute("BEGIN")
        try:
            latest_preflight = await _fetch_latest_run_for_mode(db, "preflight")
            latest_suite = await _fetch_latest_run_for_mode(db, "suite")
            recent_runs = (
                await _fetch_recent_runs(db, limit) if limit > 0 else []
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    return ComicVerificationSummaryResponse(
        latest_preflight=latest_preflight,
        latest_suite=latest_suite,
        recent_runs=recent_runs,
    )
