"""Persistence helpers for comic teaser shot registry state."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, cast

from app.db import get_db
from app.models import (
    AnimationCurrentShotResponse,
    AnimationShotResponse,
    AnimationShotVariantResponse,
    animation_shot_response_from_row,
    animation_shot_variant_response_from_row,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def resolve_or_create_current_animation_shot(
    *,
    episode_id: str,
    scene_panel_id: str,
    selected_render_asset_id: str,
    generation_id: str | None,
    source_kind: str = "comic_selected_render",
) -> AnimationShotResponse:
    now = _now_iso()
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            """
            SELECT *
            FROM animation_shots
            WHERE selected_render_asset_id = ?
            """,
            (selected_render_asset_id,),
        )
        existing = await cursor.fetchone()
        if existing is not None:
            if not bool(existing.get("is_current")):
                await db.execute(
                    """
                    UPDATE animation_shots
                    SET is_current = 0,
                        updated_at = ?
                    WHERE scene_panel_id = ?
                      AND id != ?
                      AND is_current = 1
                    """,
                    (
                        now,
                        scene_panel_id,
                        existing["id"],
                    ),
                )
                await db.execute(
                    """
                    UPDATE animation_shots
                    SET is_current = 1,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        now,
                        existing["id"],
                    ),
                )
                await db.commit()
                refresh = await db.execute(
                    "SELECT * FROM animation_shots WHERE id = ?",
                    (existing["id"],),
                )
                existing = await refresh.fetchone()
            else:
                await db.commit()
            if existing is None:
                raise RuntimeError("Failed to reload existing animation_shot")
            return animation_shot_response_from_row(existing)

        shot_id = str(uuid.uuid4())
        await db.execute(
            """
            UPDATE animation_shots
            SET is_current = 0,
                updated_at = ?
            WHERE scene_panel_id = ?
              AND is_current = 1
            """,
            (
                now,
                scene_panel_id,
            ),
        )
        await db.execute(
            """
            INSERT INTO animation_shots (
                id,
                source_kind,
                episode_id,
                scene_panel_id,
                selected_render_asset_id,
                generation_id,
                is_current,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shot_id,
                source_kind,
                episode_id,
                scene_panel_id,
                selected_render_asset_id,
                generation_id,
                1,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM animation_shots WHERE id = ?",
            (shot_id,),
        )
        created = await cursor.fetchone()

    if created is None:
        raise RuntimeError("Failed to create animation_shot")
    return animation_shot_response_from_row(created)


async def create_animation_shot_variant(
    *,
    animation_shot_id: str,
    animation_job_id: str,
    preset_id: str,
    launch_reason: str,
    status: str,
    output_path: str | None = None,
    error_message: str | None = None,
    completed_at: str | None = None,
    variant_id: str | None = None,
) -> AnimationShotVariantResponse:
    now = _now_iso()
    created_id = variant_id or str(uuid.uuid4())

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO animation_shot_variants (
                id,
                animation_shot_id,
                animation_job_id,
                preset_id,
                launch_reason,
                status,
                output_path,
                error_message,
                created_at,
                completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_id,
                animation_shot_id,
                animation_job_id,
                preset_id,
                launch_reason,
                status,
                output_path,
                error_message,
                now,
                completed_at,
            ),
        )
        await db.execute(
            """
            UPDATE animation_shots
            SET updated_at = ?
            WHERE id = ?
            """,
            (
                now,
                animation_shot_id,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            """
            SELECT *
            FROM animation_shot_variants
            WHERE id = ?
            """,
            (created_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise RuntimeError("Failed to create animation_shot_variant")
    return animation_shot_variant_response_from_row(row)


async def update_animation_shot_variant_from_job(
    animation_job_id: str,
) -> AnimationShotVariantResponse | None:
    now = _now_iso()
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT
                v.*,
                j.status AS job_status,
                j.output_path AS job_output_path,
                j.error_message AS job_error_message,
                j.completed_at AS job_completed_at
            FROM animation_shot_variants AS v
            JOIN animation_jobs AS j ON j.id = v.animation_job_id
            WHERE v.animation_job_id = ?
            """,
            (animation_job_id,),
        )
        current = await cursor.fetchone()
        if current is None:
            return None

        await db.execute(
            """
            UPDATE animation_shot_variants
            SET status = ?,
                output_path = ?,
                error_message = ?,
                completed_at = ?
            WHERE animation_job_id = ?
            """,
            (
                current["job_status"],
                current["job_output_path"],
                current["job_error_message"],
                current["job_completed_at"],
                animation_job_id,
            ),
        )
        await db.execute(
            """
            UPDATE animation_shots
            SET updated_at = ?
            WHERE id = ?
            """,
            (
                now,
                current["animation_shot_id"],
            ),
        )
        await db.commit()

        refresh = await db.execute(
            """
            SELECT *
            FROM animation_shot_variants
            WHERE animation_job_id = ?
            """,
            (animation_job_id,),
        )
        row = await refresh.fetchone()

    if row is None:
        raise RuntimeError("Failed to refresh animation_shot_variant")
    return animation_shot_variant_response_from_row(row)


async def get_current_animation_shot(
    *,
    scene_panel_id: str,
    selected_render_asset_id: str,
    limit: int = 8,
) -> AnimationCurrentShotResponse:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT *
            FROM animation_shots
            WHERE scene_panel_id = ?
              AND selected_render_asset_id = ?
            ORDER BY is_current DESC, created_at DESC
            LIMIT 1
            """,
            (
                scene_panel_id,
                selected_render_asset_id,
            ),
        )
        shot_row = await cursor.fetchone()
        if shot_row is None:
            return AnimationCurrentShotResponse()

        variant_cursor = await db.execute(
            """
            SELECT *
            FROM animation_shot_variants
            WHERE animation_shot_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (
                shot_row["id"],
                limit,
            ),
        )
        variant_rows = await variant_cursor.fetchall()

    return AnimationCurrentShotResponse(
        shot=animation_shot_response_from_row(shot_row),
        variants=[
            animation_shot_variant_response_from_row(cast(dict[str, Any], row))
            for row in variant_rows
        ],
    )
