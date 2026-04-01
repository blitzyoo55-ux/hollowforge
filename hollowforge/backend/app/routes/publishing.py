"""Publishing pipeline endpoints for ready-to-go content operations."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status

from app.config import settings
from app.db import get_db
from app.models import (
    AnimationCandidateResponse,
    AnimationCandidateUpdate,
    CaptionGenerateRequest,
    CaptionVariantResponse,
    EngagementSnapshotCreate,
    EngagementSnapshotResponse,
    PublishJobCreate,
    PublishJobResponse,
    PublishJobUpdate,
    ReadyPublishItemResponse,
    PublishingReadinessResponse,
)
from app.services.caption_service import (
    generate_caption_from_image_bytes,
    mime_type_from_image_path,
)
from app.services.publishing_service import (
    create_or_reuse_draft_publish_job,
    list_publish_jobs_for_generation,
    list_ready_publish_items as list_ready_publish_items_service,
)

router = APIRouter(prefix="/api/v1/publishing", tags=["publishing"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_generation_image_path(image_path: str) -> Path:
    candidate = (settings.DATA_DIR / image_path).resolve()
    data_root = settings.DATA_DIR.resolve()
    try:
        candidate.relative_to(data_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsafe image path",
        ) from exc
    return candidate


def _row_to_caption(row: dict[str, Any]) -> CaptionVariantResponse:
    return CaptionVariantResponse(
        id=row["id"],
        generation_id=row["generation_id"],
        channel=row["channel"],
        platform=row["platform"],
        provider=row["provider"],
        model=row["model"],
        prompt_version=row["prompt_version"],
        tone=row["tone"],
        story=row["story"],
        hashtags=row["hashtags"],
        approved=bool(row.get("approved", 0)),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


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


def _row_to_engagement_snapshot(row: dict[str, Any]) -> EngagementSnapshotResponse:
    detail_json = row.get("detail_json")
    parsed_detail: dict[str, Any] | None = None
    if isinstance(detail_json, str) and detail_json.strip():
        try:
            parsed = json.loads(detail_json)
            if isinstance(parsed, dict):
                parsed_detail = parsed
        except json.JSONDecodeError:
            parsed_detail = None

    return EngagementSnapshotResponse(
        id=row["id"],
        publish_job_id=row["publish_job_id"],
        captured_at=row["captured_at"],
        likes=int(row.get("likes") or 0),
        replies=int(row.get("replies") or 0),
        reposts=int(row.get("reposts") or 0),
        bookmarks=int(row.get("bookmarks") or 0),
        impressions=int(row.get("impressions") or 0),
        detail_json=parsed_detail,
    )


def _row_to_animation_candidate(row: dict[str, Any]) -> AnimationCandidateResponse:
    return AnimationCandidateResponse(
        id=row["id"],
        generation_id=row["generation_id"],
        publish_job_id=row.get("publish_job_id"),
        trigger_source=row["trigger_source"],
        trigger_score=float(row.get("trigger_score") or 0),
        target_tool=row["target_tool"],
        status=row["status"],
        notes=row.get("notes"),
        approved_at=row.get("approved_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _compute_engagement_score(payload: EngagementSnapshotCreate) -> float:
    return round(
        float(payload.likes)
        + float(payload.replies * 2)
        + float(payload.reposts * 3)
        + float(payload.bookmarks * 4)
        + float(payload.impressions) / 500.0,
        2,
    )


def _get_publishing_readiness() -> PublishingReadinessResponse:
    caption_generation_ready = bool(settings.OPENROUTER_API_KEY.strip())
    missing_requirements: list[str] = []
    degraded_mode: Literal["full", "draft_only"] = "full"

    if not caption_generation_ready:
        missing_requirements.append("OPENROUTER_API_KEY")
        degraded_mode = "draft_only"

    return PublishingReadinessResponse(
        caption_generation_ready=caption_generation_ready,
        draft_publish_ready=True,
        degraded_mode=degraded_mode,
        provider=settings.MARKETING_PROVIDER_NAME,
        model=settings.MARKETING_MODEL,
        missing_requirements=missing_requirements,
        notes=[],
    )


@router.get("/readiness", response_model=PublishingReadinessResponse)
async def get_publishing_readiness() -> PublishingReadinessResponse:
    return _get_publishing_readiness()


async def _require_generation(generation_id: str) -> dict[str, Any]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT id, image_path, thumbnail_path, checkpoint, prompt, publish_approved, created_at
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )
    return row


@router.get("/ready-items", response_model=list[ReadyPublishItemResponse])
async def list_ready_publish_items(
    limit: int = Query(default=100, ge=1, le=500),
    generation_id: list[str] | None = Query(default=None),
) -> list[ReadyPublishItemResponse]:
    return await list_ready_publish_items_service(
        limit=limit,
        selected_generation_ids=generation_id,
    )


@router.get(
    "/generations/{generation_id}/captions",
    response_model=list[CaptionVariantResponse],
)
async def list_caption_variants(generation_id: str) -> list[CaptionVariantResponse]:
    await _require_generation(generation_id)
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT *
            FROM caption_variants
            WHERE generation_id = ?
            ORDER BY approved DESC, updated_at DESC
            """,
            (generation_id,),
        )
        rows = await cursor.fetchall()
    return [_row_to_caption(row) for row in rows]


@router.post(
    "/generations/{generation_id}/captions/generate",
    response_model=CaptionVariantResponse,
)
async def generate_caption_variant(
    generation_id: str,
    payload: CaptionGenerateRequest,
) -> CaptionVariantResponse:
    readiness = _get_publishing_readiness()
    if not readiness.caption_generation_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Caption generation unavailable: OPENROUTER_API_KEY is not configured",
        )

    generation = await _require_generation(generation_id)
    image_path = generation.get("image_path")
    if not isinstance(image_path, str) or not image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation has no source image",
        )

    image_file_path = _resolve_generation_image_path(image_path)
    if not image_file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found",
        )

    image_bytes = await asyncio.to_thread(image_file_path.read_bytes)
    caption = await generate_caption_from_image_bytes(
        image_bytes,
        mime_type_from_image_path(image_file_path.name),
        platform=payload.platform,
        tone=payload.tone,
    )

    now = _now_iso()
    caption_id = str(uuid4())
    async with get_db() as db:
        if payload.approved:
            await db.execute(
                """
                UPDATE caption_variants
                SET approved = 0, updated_at = ?
                WHERE generation_id = ? AND channel = ? AND platform = ?
                """,
                (now, generation_id, payload.channel, payload.platform),
            )

        await db.execute(
            """
            INSERT INTO caption_variants (
                id,
                generation_id,
                channel,
                platform,
                provider,
                model,
                prompt_version,
                tone,
                story,
                hashtags,
                approved,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                caption_id,
                generation_id,
                payload.channel,
                payload.platform,
                settings.MARKETING_PROVIDER_NAME,
                settings.MARKETING_MODEL,
                settings.MARKETING_PROMPT_VERSION,
                payload.tone,
                caption["story"],
                caption["hashtags"],
                1 if payload.approved else 0,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM caption_variants WHERE id = ?",
            (caption_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist generated caption",
        )
    return _row_to_caption(row)


@router.post("/captions/{caption_id}/approve", response_model=CaptionVariantResponse)
async def approve_caption_variant(caption_id: str) -> CaptionVariantResponse:
    now = _now_iso()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM caption_variants WHERE id = ?",
            (caption_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Caption variant {caption_id} not found",
            )

        await db.execute(
            """
            UPDATE caption_variants
            SET approved = 0, updated_at = ?
            WHERE generation_id = ? AND channel = ? AND platform = ?
            """,
            (now, row["generation_id"], row["channel"], row["platform"]),
        )
        await db.execute(
            """
            UPDATE caption_variants
            SET approved = 1, updated_at = ?
            WHERE id = ?
            """,
            (now, caption_id),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM caption_variants WHERE id = ?",
            (caption_id,),
        )
        approved_row = await cursor.fetchone()

    if approved_row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve caption variant",
        )
    return _row_to_caption(approved_row)


@router.post("/posts", response_model=PublishJobResponse, status_code=status.HTTP_201_CREATED)
async def create_publish_job(payload: PublishJobCreate) -> PublishJobResponse:
    await _require_generation(payload.generation_id)

    if payload.caption_variant_id:
        async with get_db() as db:
            cursor = await db.execute(
                """
                SELECT id
                FROM caption_variants
                WHERE id = ? AND generation_id = ?
                """,
                (payload.caption_variant_id, payload.generation_id),
            )
            if await cursor.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Caption variant does not belong to generation",
                )

    if payload.status == "draft":
        return await create_or_reuse_draft_publish_job(
            generation_id=payload.generation_id,
            platform=payload.platform,
            caption_variant_id=payload.caption_variant_id,
            notes=payload.notes,
        )

    now = _now_iso()
    publish_job_id = str(uuid4())
    async with get_db() as db:
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
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                publish_job_id,
                payload.generation_id,
                payload.caption_variant_id,
                payload.platform,
                payload.status,
                payload.scheduled_at,
                payload.external_post_id,
                payload.external_post_url,
                payload.notes,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM publish_jobs WHERE id = ?",
            (publish_job_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create publish job",
        )
    return _row_to_publish_job(row)


@router.get(
    "/generations/{generation_id}/publish-jobs",
    response_model=list[PublishJobResponse],
)
async def list_generation_publish_jobs(generation_id: str) -> list[PublishJobResponse]:
    await _require_generation(generation_id)
    return await list_publish_jobs_for_generation(generation_id)


@router.patch("/posts/{publish_job_id}", response_model=PublishJobResponse)
async def update_publish_job(
    publish_job_id: str,
    payload: PublishJobUpdate,
) -> PublishJobResponse:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM publish_jobs WHERE id = ?",
            (publish_job_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Publish job {publish_job_id} not found",
            )

        current = dict(row)
        now = _now_iso()
        next_status = payload.status or current["status"]
        next_scheduled_at = payload.scheduled_at if payload.scheduled_at is not None else current.get("scheduled_at")
        next_published_at = payload.published_at if payload.published_at is not None else current.get("published_at")
        next_external_post_id = (
            payload.external_post_id
            if payload.external_post_id is not None
            else current.get("external_post_id")
        )
        next_external_post_url = (
            payload.external_post_url
            if payload.external_post_url is not None
            else current.get("external_post_url")
        )
        next_notes = payload.notes if payload.notes is not None else current.get("notes")

        await db.execute(
            """
            UPDATE publish_jobs
            SET status = ?,
                scheduled_at = ?,
                published_at = ?,
                external_post_id = ?,
                external_post_url = ?,
                notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                next_scheduled_at,
                next_published_at,
                next_external_post_id,
                next_external_post_url,
                next_notes,
                now,
                publish_job_id,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM publish_jobs WHERE id = ?",
            (publish_job_id,),
        )
        updated_row = await cursor.fetchone()

    if updated_row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update publish job",
        )
    return _row_to_publish_job(updated_row)


@router.post("/posts/{publish_job_id}/engagement")
async def record_engagement_snapshot(
    publish_job_id: str,
    payload: EngagementSnapshotCreate,
) -> dict[str, Any]:
    captured_at = _now_iso()
    score = _compute_engagement_score(payload)
    snapshot_id: int | None = None

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM publish_jobs WHERE id = ?",
            (publish_job_id,),
        )
        publish_job = await cursor.fetchone()
        if publish_job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Publish job {publish_job_id} not found",
            )

        detail_json = (
            json.dumps(payload.detail_json, ensure_ascii=False)
            if payload.detail_json is not None
            else None
        )

        cursor = await db.execute(
            """
            INSERT INTO engagement_snapshots (
                publish_job_id,
                captured_at,
                likes,
                replies,
                reposts,
                bookmarks,
                impressions,
                detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                publish_job_id,
                captured_at,
                payload.likes,
                payload.replies,
                payload.reposts,
                payload.bookmarks,
                payload.impressions,
                detail_json,
            ),
        )
        snapshot_id = cursor.lastrowid

        candidate: dict[str, Any] | None = None
        should_suggest_animation = (
            score >= settings.PUBLISH_ANIMATION_SCORE_THRESHOLD
            or payload.bookmarks >= settings.PUBLISH_ANIMATION_BOOKMARK_THRESHOLD
        )

        if should_suggest_animation:
            cursor = await db.execute(
                """
                SELECT *
                FROM animation_candidates
                WHERE generation_id = ? AND publish_job_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (publish_job["generation_id"], publish_job_id),
            )
            existing_candidate = await cursor.fetchone()
            notes = (
                f"Auto-suggested from engagement score {score:.2f} "
                f"(likes={payload.likes}, replies={payload.replies}, reposts={payload.reposts}, "
                f"bookmarks={payload.bookmarks}, impressions={payload.impressions})"
            )

            if existing_candidate is None:
                candidate_id = str(uuid4())
                await db.execute(
                    """
                    INSERT INTO animation_candidates (
                        id,
                        generation_id,
                        publish_job_id,
                        trigger_source,
                        trigger_score,
                        target_tool,
                        status,
                        notes,
                        approved_at,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, 'engagement', ?, ?, 'suggested', ?, NULL, ?, ?)
                    """,
                    (
                        candidate_id,
                        publish_job["generation_id"],
                        publish_job_id,
                        score,
                        settings.PUBLISH_DEFAULT_ANIMATION_TOOL,
                        notes,
                        captured_at,
                        captured_at,
                    ),
                )
                cursor = await db.execute(
                    "SELECT * FROM animation_candidates WHERE id = ?",
                    (candidate_id,),
                )
                candidate = await cursor.fetchone()
            else:
                await db.execute(
                    """
                    UPDATE animation_candidates
                    SET trigger_score = ?,
                        notes = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        max(score, float(existing_candidate.get("trigger_score") or 0)),
                        notes,
                        captured_at,
                        existing_candidate["id"],
                    ),
                )
                cursor = await db.execute(
                    "SELECT * FROM animation_candidates WHERE id = ?",
                    (existing_candidate["id"],),
                )
                candidate = await cursor.fetchone()

        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM engagement_snapshots WHERE id = ?",
            (snapshot_id,),
        )
        snapshot_row = await cursor.fetchone()

    if snapshot_row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist engagement snapshot",
        )

    return {
        "snapshot": _row_to_engagement_snapshot(snapshot_row),
        "engagement_score": score,
        "animation_candidate": _row_to_animation_candidate(candidate) if candidate else None,
    }


@router.get(
    "/animation-candidates",
    response_model=list[AnimationCandidateResponse],
)
async def list_animation_candidates(
    status_filter: str | None = Query(default=None),
) -> list[AnimationCandidateResponse]:
    async with get_db() as db:
        if status_filter:
            cursor = await db.execute(
                """
                SELECT *
                FROM animation_candidates
                WHERE status = ?
                ORDER BY updated_at DESC
                """,
                (status_filter,),
            )
        else:
            cursor = await db.execute(
                """
                SELECT *
                FROM animation_candidates
                ORDER BY updated_at DESC
                """
            )
        rows = await cursor.fetchall()
    return [_row_to_animation_candidate(row) for row in rows]


@router.patch(
    "/animation-candidates/{candidate_id}",
    response_model=AnimationCandidateResponse,
)
async def update_animation_candidate(
    candidate_id: str,
    payload: AnimationCandidateUpdate,
) -> AnimationCandidateResponse:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM animation_candidates WHERE id = ?",
            (candidate_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Animation candidate {candidate_id} not found",
            )

        current = dict(row)
        now = _now_iso()
        next_status = payload.status or current["status"]
        next_target_tool = payload.target_tool or current["target_tool"]
        next_notes = payload.notes if payload.notes is not None else current.get("notes")
        next_approved_at = current.get("approved_at")
        if next_status == "approved" and not next_approved_at:
            next_approved_at = now

        await db.execute(
            """
            UPDATE animation_candidates
            SET status = ?,
                target_tool = ?,
                notes = ?,
                approved_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_status,
                next_target_tool,
                next_notes,
                next_approved_at,
                now,
                candidate_id,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM animation_candidates WHERE id = ?",
            (candidate_id,),
        )
        updated_row = await cursor.fetchone()

    if updated_row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update animation candidate",
        )
    return _row_to_animation_candidate(updated_row)
