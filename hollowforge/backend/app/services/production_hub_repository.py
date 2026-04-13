"""Repository helpers for shared HollowForge production hub records."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, cast

from app.db import get_db
from app.models import (
    ProductionAnimationTrackLinkResponse,
    ProductionComicTrackLinkResponse,
    ProductionEpisodeCreate,
    ProductionEpisodeDetailResponse,
    ProductionSeriesCreate,
    ProductionSeriesResponse,
    ProductionWorkCreate,
    ProductionWorkResponse,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _encode_json_list(values: list[Any]) -> str:
    return json.dumps(values, separators=(",", ":"), ensure_ascii=False)


def _decode_json_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON list in {field_name}") from exc
        if not isinstance(parsed, list):
            raise ValueError(f"Invalid JSON list in {field_name}")
        return [str(item) for item in parsed]
    raise ValueError(f"Invalid JSON list in {field_name}")


def _work_response(row: dict[str, Any]) -> ProductionWorkResponse:
    return ProductionWorkResponse.model_validate(row)


def _series_response(row: dict[str, Any]) -> ProductionSeriesResponse:
    return ProductionSeriesResponse.model_validate(row)


def _episode_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["target_outputs"] = _decode_json_list(
        payload.get("target_outputs"),
        field_name="production_episodes.target_outputs",
    )
    return payload


async def _resolve_comic_track(
    production_episode_id: str,
) -> Optional[ProductionComicTrackLinkResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, status, target_output, character_id
            FROM comic_episodes
            WHERE production_episode_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (production_episode_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return ProductionComicTrackLinkResponse.model_validate(dict(row))


async def _resolve_animation_track(
    production_episode_id: str,
) -> Optional[ProductionAnimationTrackLinkResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, content_mode, policy_profile_id, shot_count, executor_policy
            FROM sequence_blueprints
            WHERE production_episode_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (production_episode_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return ProductionAnimationTrackLinkResponse.model_validate(dict(row))


async def _get_work_row(work_id: str) -> Optional[dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM works WHERE id = ?", (work_id,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return cast(dict[str, Any], row)


async def _get_series_row(series_id: str) -> Optional[dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM series WHERE id = ?", (series_id,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return cast(dict[str, Any], row)


async def create_work(payload: ProductionWorkCreate) -> ProductionWorkResponse:
    now = _now_iso()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO works (
                id,
                title,
                format_family,
                default_content_mode,
                status,
                canon_notes,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.id,
                payload.title,
                payload.format_family,
                payload.default_content_mode,
                payload.status,
                payload.canon_notes,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM works WHERE id = ?", (payload.id,))
        row = await cursor.fetchone()
    return _work_response(cast(dict[str, Any], row))


async def create_series(payload: ProductionSeriesCreate) -> ProductionSeriesResponse:
    work_row = await _get_work_row(payload.work_id)
    if work_row is None:
        raise ValueError(f"Unknown production work: {payload.work_id}")

    now = _now_iso()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO series (
                id,
                work_id,
                title,
                delivery_mode,
                audience_mode,
                visual_identity_notes,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.id,
                payload.work_id,
                payload.title,
                payload.delivery_mode,
                payload.audience_mode,
                payload.visual_identity_notes,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM series WHERE id = ?", (payload.id,))
        row = await cursor.fetchone()
    return _series_response(cast(dict[str, Any], row))


async def create_production_episode(
    payload: ProductionEpisodeCreate,
) -> ProductionEpisodeDetailResponse:
    work_row = await _get_work_row(payload.work_id)
    if work_row is None:
        raise ValueError(f"Unknown production work: {payload.work_id}")

    if payload.series_id is not None:
        series_row = await _get_series_row(payload.series_id)
        if series_row is None:
            raise ValueError(f"Unknown production series: {payload.series_id}")
        if cast(str, series_row["work_id"]) != payload.work_id:
            raise ValueError(
                f"Production series {payload.series_id} does not belong to work {payload.work_id}"
            )

    now = _now_iso()
    production_episode_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO production_episodes (
                id,
                work_id,
                series_id,
                title,
                synopsis,
                content_mode,
                target_outputs,
                continuity_summary,
                status,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                production_episode_id,
                payload.work_id,
                payload.series_id,
                payload.title,
                payload.synopsis,
                payload.content_mode,
                _encode_json_list(payload.target_outputs),
                payload.continuity_summary,
                payload.status,
                now,
                now,
            ),
        )
        await db.commit()

    detail = await get_production_episode_detail(production_episode_id)
    if detail is None:
        raise ValueError("Production episode detail missing after create")
    return detail


async def get_production_episode_detail(
    production_episode_id: str,
) -> Optional[ProductionEpisodeDetailResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM production_episodes WHERE id = ?",
            (production_episode_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None

    payload = _episode_payload(cast(dict[str, Any], row))
    payload["comic_track"] = await _resolve_comic_track(production_episode_id)
    payload["animation_track"] = await _resolve_animation_track(production_episode_id)
    return ProductionEpisodeDetailResponse.model_validate(payload)


async def list_production_episodes(
    *,
    work_id: Optional[str] = None,
) -> list[ProductionEpisodeDetailResponse]:
    clauses: list[str] = []
    params: list[Any] = []
    if work_id is not None:
        clauses.append("work_id = ?")
        params.append(work_id)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT *
            FROM production_episodes
            {where_clause}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        )
        rows = await cursor.fetchall()

    details: list[ProductionEpisodeDetailResponse] = []
    for row in rows:
        payload = _episode_payload(cast(dict[str, Any], row))
        production_episode_id = cast(str, payload["id"])
        payload["comic_track"] = await _resolve_comic_track(production_episode_id)
        payload["animation_track"] = await _resolve_animation_track(production_episode_id)
        details.append(ProductionEpisodeDetailResponse.model_validate(payload))
    return details
