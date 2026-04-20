"""Thin repository helpers for HollowForge comic episode state."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, cast

import aiosqlite

from app.db import get_db
from app.models import (
    ComicCharacterResponse,
    ComicCharacterVersionResponse,
    ComicEpisodeDraft,
    ComicEpisodeCreate,
    ComicEpisodeDetailResponse,
    ComicEpisodeResponse,
    ComicEpisodeSceneResponse,
    ComicEpisodeSummaryResponse,
    ComicPageAssemblyResponse,
    ComicSceneDetailResponse,
    ComicScenePanelResponse,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_json_list(value: str | None, *, field_name: str) -> list[Any]:
    if value is None:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON list in {field_name}") from exc
    if not isinstance(parsed, list):
        raise ValueError(f"Invalid JSON list in {field_name}")
    return parsed


def _decode_json_dict(value: str | None, *, field_name: str) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON object in {field_name}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"Invalid JSON object in {field_name}")
    return parsed


def _encode_json_list(values: list[Any]) -> str:
    return json.dumps(values, separators=(",", ":"), ensure_ascii=False)


async def _validate_episode_references(
    db: aiosqlite.Connection,
    *,
    character_id: str,
    character_version_id: str,
) -> None:
    character_cursor = await db.execute(
        "SELECT id FROM characters WHERE id = ?",
        (character_id,),
    )
    character_row = await character_cursor.fetchone()
    if character_row is None:
        raise ValueError(f"Unknown comic character: {character_id}")

    version_cursor = await db.execute(
        "SELECT character_id FROM character_versions WHERE id = ?",
        (character_version_id,),
    )
    version_row = await version_cursor.fetchone()
    if version_row is None:
        raise ValueError(f"Unknown comic character version: {character_version_id}")

    if cast(str, version_row["character_id"]) != character_id:
        raise ValueError(
            f"Comic character version {character_version_id} does not belong to character {character_id}"
        )


async def _get_character_id_for_version(
    db: aiosqlite.Connection,
    *,
    character_version_id: str,
) -> str:
    version_cursor = await db.execute(
        "SELECT character_id FROM character_versions WHERE id = ?",
        (character_version_id,),
    )
    version_row = await version_cursor.fetchone()
    if version_row is None:
        raise ValueError(f"Unknown comic character version: {character_version_id}")
    return cast(str, version_row["character_id"])


async def _get_character_context_for_version(
    db: aiosqlite.Connection,
    *,
    character_version_id: str,
) -> tuple[str, str]:
    version_cursor = await db.execute(
        """
        SELECT cv.character_id, c.slug
        FROM character_versions cv
        JOIN characters c ON c.id = cv.character_id
        WHERE cv.id = ?
        """,
        (character_version_id,),
    )
    version_row = await version_cursor.fetchone()
    if version_row is None:
        raise ValueError(f"Unknown comic character version: {character_version_id}")
    return (
        cast(str, version_row["character_id"]),
        cast(str, version_row["slug"]),
    )


def _character_response(row: dict[str, Any]) -> ComicCharacterResponse:
    return ComicCharacterResponse.model_validate(row)


def _character_version_response(row: dict[str, Any]) -> ComicCharacterVersionResponse:
    return ComicCharacterVersionResponse.model_validate(row)


def _episode_response(row: dict[str, Any]) -> ComicEpisodeResponse:
    return ComicEpisodeResponse.model_validate(row)


def _scene_response(row: dict[str, Any]) -> ComicEpisodeSceneResponse:
    payload = dict(row)
    payload["involved_character_ids"] = _decode_json_list(
        cast(Optional[str], payload.get("involved_character_ids")),
        field_name="comic_episode_scenes.involved_character_ids",
    )
    return ComicEpisodeSceneResponse.model_validate(payload)


def _panel_response(row: dict[str, Any]) -> ComicScenePanelResponse:
    return ComicScenePanelResponse.model_validate(row)


def _page_response(row: dict[str, Any]) -> ComicPageAssemblyResponse:
    payload = dict(row)
    payload["ordered_panel_ids"] = _decode_json_list(
        cast(Optional[str], payload.get("ordered_panel_ids")),
        field_name="comic_page_assemblies.ordered_panel_ids",
    )
    payload["manuscript_profile_id"] = cast(
        str,
        payload.get("manuscript_profile_id") or "jp_manga_rightbound_v1",
    )
    payload["export_manifest"] = _decode_json_dict(
        cast(Optional[str], payload.get("export_manifest")),
        field_name="comic_page_assemblies.export_manifest",
    )
    return ComicPageAssemblyResponse.model_validate(payload)


async def list_comic_characters() -> list[ComicCharacterResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, slug, name, status, tier, created_at, updated_at
            FROM characters
            ORDER BY name ASC, id ASC
            """
        )
        rows = await cursor.fetchall()
    return [_character_response(cast(dict[str, Any], row)) for row in rows]


async def list_comic_character_versions(
    character_id: str | None = None,
) -> list[ComicCharacterVersionResponse]:
    params: list[Any] = []
    where_clause = ""
    if character_id is not None:
        where_clause = "WHERE character_id = ?"
        params.append(character_id)

    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT
                id,
                character_id,
                version_name,
                purpose,
                checkpoint,
                workflow_lane,
                created_at,
                updated_at
            FROM character_versions
            {where_clause}
            ORDER BY character_id ASC, created_at ASC, id ASC
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [_character_version_response(cast(dict[str, Any], row)) for row in rows]


async def create_comic_episode(
    payload: ComicEpisodeCreate,
    *,
    episode_id: str | None = None,
) -> ComicEpisodeResponse:
    now = _now_iso()
    created_id = episode_id or str(uuid.uuid4())
    async with get_db() as db:
        await _validate_episode_references(
            db,
            character_id=payload.character_id,
            character_version_id=payload.character_version_id,
        )
        await db.execute(
            """
            INSERT INTO comic_episodes (
                id,
                character_id,
                character_version_id,
                content_mode,
                work_id,
                series_id,
                production_episode_id,
                title,
                synopsis,
                source_story_plan_json,
                status,
                continuity_summary,
                canon_delta,
                target_output,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_id,
                payload.character_id,
                payload.character_version_id,
                payload.content_mode,
                payload.work_id,
                payload.series_id,
                payload.production_episode_id,
                payload.title,
                payload.synopsis,
                payload.source_story_plan_json,
                payload.status,
                payload.continuity_summary,
                payload.canon_delta,
                payload.target_output,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM comic_episodes WHERE id = ?",
            (created_id,),
        )
        row = await cursor.fetchone()
    return _episode_response(cast(dict[str, Any], row))


async def resolve_comic_character_id_for_version(character_version_id: str) -> str:
    async with get_db() as db:
        return await _get_character_id_for_version(
            db,
            character_version_id=character_version_id,
        )


async def resolve_comic_character_context_for_version(
    character_version_id: str,
) -> tuple[str, str]:
    async with get_db() as db:
        return await _get_character_context_for_version(
            db,
            character_version_id=character_version_id,
        )


async def create_comic_episode_from_draft(
    *,
    character_id: str,
    draft: ComicEpisodeDraft,
    episode_id: str | None = None,
) -> ComicEpisodeDetailResponse:
    now = _now_iso()
    created_id = episode_id or str(uuid.uuid4())

    async with get_db() as db:
        await _validate_episode_references(
            db,
            character_id=character_id,
            character_version_id=draft.character_version_id,
        )
        await db.execute(
            """
            INSERT INTO comic_episodes (
                id,
                character_id,
                character_version_id,
                content_mode,
                work_id,
                series_id,
                production_episode_id,
                title,
                synopsis,
                source_story_plan_json,
                status,
                continuity_summary,
                canon_delta,
                target_output,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_id,
                character_id,
                draft.character_version_id,
                draft.content_mode,
                draft.work_id,
                draft.series_id,
                draft.production_episode_id,
                draft.title,
                draft.synopsis,
                draft.source_story_plan_json,
                draft.status,
                draft.continuity_summary,
                draft.canon_delta,
                draft.target_output,
                now,
                now,
            ),
        )

        scene_ids: dict[int, str] = {}
        for scene in sorted(draft.scenes, key=lambda item: item.scene_no):
            scene_id = str(uuid.uuid4())
            scene_ids[scene.scene_no] = scene_id
            await db.execute(
                """
                INSERT INTO comic_episode_scenes (
                    id,
                    episode_id,
                    scene_no,
                    premise,
                    location_label,
                    tension,
                    reveal,
                    continuity_notes,
                    involved_character_ids,
                    target_panel_count,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scene_id,
                    created_id,
                    scene.scene_no,
                    scene.premise,
                    scene.location_label,
                    scene.tension,
                    scene.reveal,
                    scene.continuity_notes,
                    _encode_json_list(scene.involved_character_ids),
                    scene.target_panel_count,
                    now,
                    now,
                ),
            )

        for panel in sorted(draft.panels, key=lambda item: (item.scene_no, item.reading_order, item.panel_no)):
            scene_id = scene_ids.get(panel.scene_no)
            if scene_id is None:
                raise ValueError(
                    f"Panel scene_no {panel.scene_no} does not have a matching draft scene"
                )
            await db.execute(
                """
                INSERT INTO comic_scene_panels (
                    id,
                    episode_scene_id,
                    panel_no,
                    panel_type,
                    framing,
                    camera_intent,
                    action_intent,
                    expression_intent,
                    dialogue_intent,
                    continuity_lock,
                    page_target_hint,
                    reading_order,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    scene_id,
                    panel.panel_no,
                    panel.panel_type,
                    panel.framing,
                    panel.camera_intent,
                    panel.action_intent,
                    panel.expression_intent,
                    panel.dialogue_intent,
                    panel.continuity_lock,
                    panel.page_target_hint,
                    panel.reading_order,
                    now,
                    now,
                ),
            )

        await db.commit()

    detail = await get_comic_episode_detail(created_id)
    if detail is None:
        raise ValueError("Comic episode detail missing after draft import")
    return detail


async def list_comic_episodes(
    *,
    character_id: str | None = None,
    status: str | None = None,
    production_episode_id: str | None = None,
) -> list[ComicEpisodeSummaryResponse]:
    clauses: list[str] = []
    params: list[Any] = []
    if character_id is not None:
        clauses.append("e.character_id = ?")
        params.append(character_id)
    if status is not None:
        clauses.append("e.status = ?")
        params.append(status)
    if production_episode_id is not None:
        clauses.append("e.production_episode_id = ?")
        params.append(production_episode_id)
    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT
                e.*,
                COUNT(DISTINCT s.id) AS scene_count,
                COUNT(DISTINCT p.id) AS page_count
            FROM comic_episodes e
            LEFT JOIN comic_episode_scenes s ON s.episode_id = e.id
            LEFT JOIN comic_page_assemblies p ON p.episode_id = e.id
            {where_clause}
            GROUP BY e.id
            ORDER BY e.updated_at DESC, e.id DESC
            """,
            params,
        )
        rows = await cursor.fetchall()

    summaries: list[ComicEpisodeSummaryResponse] = []
    for row in rows:
        payload = cast(dict[str, Any], row)
        episode_payload = {key: value for key, value in payload.items() if key not in {"scene_count", "page_count"}}
        summaries.append(
            ComicEpisodeSummaryResponse(
                episode=_episode_response(episode_payload),
                scene_count=int(payload.get("scene_count") or 0),
                page_count=int(payload.get("page_count") or 0),
            )
        )
    return summaries


async def get_comic_episode_detail(
    episode_id: str,
) -> ComicEpisodeDetailResponse | None:
    async with get_db() as db:
        episode_cursor = await db.execute(
            "SELECT * FROM comic_episodes WHERE id = ?",
            (episode_id,),
        )
        episode_row = await episode_cursor.fetchone()
        if episode_row is None:
            return None

        scene_cursor = await db.execute(
            """
            SELECT * FROM comic_episode_scenes
            WHERE episode_id = ?
            ORDER BY scene_no ASC, id ASC
            """,
            (episode_id,),
        )
        scene_rows = await scene_cursor.fetchall()

        page_cursor = await db.execute(
            """
            SELECT * FROM comic_page_assemblies
            WHERE episode_id = ?
            ORDER BY page_no ASC, id ASC
            """,
            (episode_id,),
        )
        page_rows = await page_cursor.fetchall()

        remote_job_count_cursor = await db.execute(
            """
            SELECT
                p.id AS scene_panel_id,
                COUNT(j.id) AS remote_job_count,
                SUM(
                    CASE
                        WHEN j.status IN ('draft', 'queued', 'submitted', 'processing') THEN 1
                        ELSE 0
                    END
                ) AS pending_remote_job_count
            FROM comic_scene_panels p
            JOIN comic_episode_scenes s ON s.id = p.episode_scene_id
            LEFT JOIN comic_render_jobs j ON j.scene_panel_id = p.id
            WHERE s.episode_id = ?
            GROUP BY p.id
            """,
            (episode_id,),
        )
        remote_job_count_rows = await remote_job_count_cursor.fetchall()
        remote_job_counts_by_panel_id = {
            cast(str, row["scene_panel_id"]): {
                "remote_job_count": cast(Optional[int], row["remote_job_count"]) or 0,
                "pending_remote_job_count": cast(Optional[int], row["pending_remote_job_count"]) or 0,
            }
            for row in remote_job_count_rows
        }

        scenes: list[ComicSceneDetailResponse] = []
        for row in scene_rows:
            scene = _scene_response(cast(dict[str, Any], row))
            panel_cursor = await db.execute(
                """
                SELECT p.*
                FROM comic_scene_panels p
                WHERE episode_scene_id = ?
                ORDER BY p.reading_order ASC, p.id ASC
                """,
                (scene.id,),
            )
            panel_rows = await panel_cursor.fetchall()
            scenes.append(
                ComicSceneDetailResponse(
                    scene=scene,
                    panels=[
                        _panel_response({
                            **cast(dict[str, Any], panel_row),
                            **remote_job_counts_by_panel_id.get(
                                cast(str, panel_row["id"]),
                                {
                                    "remote_job_count": 0,
                                    "pending_remote_job_count": 0,
                                },
                            ),
                        })
                        for panel_row in panel_rows
                    ],
                )
            )

    return ComicEpisodeDetailResponse(
        episode=_episode_response(cast(dict[str, Any], episode_row)),
        scenes=scenes,
        pages=[_page_response(cast(dict[str, Any], row)) for row in page_rows],
    )
