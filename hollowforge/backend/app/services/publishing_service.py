"""Service helpers for publishing workbench queries and draft jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
from uuid import uuid4

from app.db import get_db
from app.models import PublishJobResponse, ReadyPublishItemResponse


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_publish_job(row: dict[str, Any]) -> PublishJobResponse:
    return PublishJobResponse(
        id=row["id"],
        generation_id=row["generation_id"],
        caption_variant_id=row.get("caption_variant_id"),
        platform=row["platform"],
        status=row["status"],
        scheduled_at=row.get("scheduled_at"),
        published_at=row.get("published_at"),
        external_post_id=row.get("external_post_id"),
        external_post_url=row.get("external_post_url"),
        notes=row.get("notes"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_ready_publish_item(row: dict[str, Any]) -> ReadyPublishItemResponse:
    return ReadyPublishItemResponse(
        generation_id=row["generation_id"],
        image_path=row.get("image_path"),
        thumbnail_path=row.get("thumbnail_path"),
        checkpoint=row["checkpoint"],
        prompt=row["prompt"],
        created_at=row["created_at"],
        approved_caption_id=row.get("approved_caption_id"),
        caption_count=int(row.get("caption_count") or 0),
        publish_job_count=int(row.get("publish_job_count") or 0),
        latest_publish_status=row.get("latest_publish_status"),
        latest_animation_status=row.get("latest_animation_status"),
        latest_animation_score=(
            float(row["latest_animation_score"])
            if row.get("latest_animation_score") is not None
            else None
        ),
    )


async def list_ready_publish_items(
    *,
    limit: int = 100,
    selected_generation_ids: Sequence[str] | None = None,
) -> list[ReadyPublishItemResponse]:
    query = """
        SELECT
            g.id AS generation_id,
            g.image_path,
            g.thumbnail_path,
            g.checkpoint,
            g.prompt,
            g.created_at,
            (
                SELECT c.id
                FROM caption_variants c
                WHERE c.generation_id = g.id
                  AND c.approved = 1
                ORDER BY c.updated_at DESC
                LIMIT 1
            ) AS approved_caption_id,
            (
                SELECT COUNT(*)
                FROM caption_variants c
                WHERE c.generation_id = g.id
            ) AS caption_count,
            (
                SELECT COUNT(*)
                FROM publish_jobs p
                WHERE p.generation_id = g.id
            ) AS publish_job_count,
            (
                SELECT p.status
                FROM publish_jobs p
                WHERE p.generation_id = g.id
                ORDER BY p.updated_at DESC
                LIMIT 1
            ) AS latest_publish_status,
            (
                SELECT a.status
                FROM animation_candidates a
                WHERE a.generation_id = g.id
                ORDER BY a.updated_at DESC
                LIMIT 1
            ) AS latest_animation_status,
            (
                SELECT a.trigger_score
                FROM animation_candidates a
                WHERE a.generation_id = g.id
                ORDER BY a.updated_at DESC
                LIMIT 1
            ) AS latest_animation_score
        FROM generations g
        WHERE g.publish_approved = 1
    """
    params: list[Any] = []

    if selected_generation_ids:
        placeholders = ", ".join("?" for _ in selected_generation_ids)
        query += f" AND g.id IN ({placeholders})"
        params.extend(selected_generation_ids)

    query += """
        ORDER BY COALESCE(g.curated_at, g.created_at) DESC
        LIMIT ?
    """
    params.append(limit)

    async with get_db() as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

    return [_row_to_ready_publish_item(row) for row in rows]


async def list_publish_jobs_for_generation(generation_id: str) -> list[PublishJobResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT *
            FROM publish_jobs
            WHERE generation_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            (generation_id,),
        )
        rows = await cursor.fetchall()

    return [_row_to_publish_job(row) for row in rows]


async def create_or_reuse_draft_publish_job(
    *,
    generation_id: str,
    platform: str,
    caption_variant_id: str | None = None,
    notes: str | None = None,
) -> PublishJobResponse:
    """Return the existing draft for a generation/platform pair or create one.

    Reuse is intentionally strict: if a draft already exists, new
    ``caption_variant_id`` and ``notes`` inputs are ignored so callers get the
    original persisted draft back unchanged.
    """
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                """
                SELECT *
                FROM publish_jobs
                WHERE generation_id = ? AND platform = ? AND status = 'draft'
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (generation_id, platform),
            )
            existing_row = await cursor.fetchone()
            if existing_row is not None:
                await db.rollback()
                return _row_to_publish_job(existing_row)

            now = _now_iso()
            publish_job_id = str(uuid4())
            await db.execute(
                """
                INSERT INTO publish_jobs (
                    id,
                    generation_id,
                    caption_variant_id,
                    platform,
                    status,
                    scheduled_at,
                    published_at,
                    external_post_id,
                    external_post_url,
                    notes,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, 'draft', NULL, NULL, NULL, NULL, ?, ?, ?)
                """,
                (
                    publish_job_id,
                    generation_id,
                    caption_variant_id,
                    platform,
                    notes,
                    now,
                    now,
                ),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        cursor = await db.execute(
            "SELECT * FROM publish_jobs WHERE id = ?",
            (publish_job_id,),
        )
        created_row = await cursor.fetchone()

    if created_row is None:
        raise RuntimeError("Failed to create draft publish job")

    return _row_to_publish_job(created_row)
