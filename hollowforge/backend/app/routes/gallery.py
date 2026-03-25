"""Gallery browsing and deletion endpoints."""

from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.db import get_db
from app.models import GenerationResponse, LoraInput, PaginatedResponse

router = APIRouter(prefix="/api/v1/gallery", tags=["gallery"])


def _parse_json(val: Optional[str], default: Any = None) -> Any:
    if val is None:
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def _row_to_response(row: dict) -> GenerationResponse:
    loras_raw = _parse_json(row.get("loras"), [])
    loras = [LoraInput(**l) if isinstance(l, dict) else l for l in loras_raw]
    dreamactor_path: str | None = None
    dreamactor_status: str | None = None
    dreamactor_task_id: str | None = None
    try:
        dreamactor_path = row.get("dreamactor_path")
        dreamactor_status = row.get("dreamactor_status")
        dreamactor_task_id = row.get("dreamactor_task_id")
    except Exception:
        # Backward compatibility for DBs where migration 012 is not applied yet.
        dreamactor_path = None
        dreamactor_status = None
        dreamactor_task_id = None

    return GenerationResponse(
        id=row["id"],
        prompt=row["prompt"],
        negative_prompt=row.get("negative_prompt"),
        checkpoint=row["checkpoint"],
        loras=loras,
        seed=row["seed"],
        steps=row["steps"],
        cfg=row["cfg"],
        width=row["width"],
        height=row["height"],
        sampler=row["sampler"],
        scheduler=row["scheduler"],
        clip_skip=row.get("clip_skip"),
        status=row["status"],
        image_path=row.get("image_path"),
        watermarked_path=row.get("watermarked_path"),
        upscaled_image_path=row.get("upscaled_image_path"),
        adetailed_path=row.get("adetailed_path"),
        hiresfix_path=row.get("hiresfix_path"),
        dreamactor_path=dreamactor_path,
        dreamactor_task_id=dreamactor_task_id,
        dreamactor_status=dreamactor_status,
        upscaled_preview_path=row.get("upscaled_preview_path"),
        upscale_model=row.get("upscale_model"),
        thumbnail_path=row.get("thumbnail_path"),
        workflow_path=row.get("workflow_path"),
        generation_time_sec=row.get("generation_time_sec"),
        tags=_parse_json(row.get("tags")),
        preset_id=row.get("preset_id"),
        notes=row.get("notes"),
        source_id=row.get("source_id"),
        comfyui_prompt_id=row.get("comfyui_prompt_id"),
        error_message=row.get("error_message"),
        is_favorite=bool(row.get("is_favorite", 0)),
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
        quality_score=row.get("quality_score"),
        quality_ai_score=row.get("quality_ai_score"),
        publish_approved=row.get("publish_approved", 0),
    )


def _resolve_public_file(base_dir: Path, rel: str) -> Path | None:
    rel_path = Path(rel)
    if rel_path.is_absolute() or not rel_path.parts:
        return None
    if rel_path.parts[0] not in {"images", "thumbs", "workflows"}:
        return None

    full_path = (base_dir / rel_path).resolve()
    try:
        full_path.relative_to(base_dir.resolve())
    except ValueError:
        return None

    return full_path


def _calculate_streak(
    active_dates: list[str],
    today: date,
) -> dict[str, int]:
    if not active_dates:
        return {"current_days": 0, "longest_days": 0}

    parsed = sorted(
        {
            datetime.strptime(day, "%Y-%m-%d").date()
            for day in active_dates
            if day
        }
    )
    if not parsed:
        return {"current_days": 0, "longest_days": 0}

    longest = 1
    run = 1
    for idx in range(1, len(parsed)):
        if parsed[idx] - parsed[idx - 1] == timedelta(days=1):
            run += 1
        else:
            run = 1
        longest = max(longest, run)

    date_set = set(parsed)
    cursor = today
    current = 0
    while cursor in date_set:
        current += 1
        cursor -= timedelta(days=1)

    return {"current_days": current, "longest_days": longest}


@router.get("/timeline")
async def get_timeline(
    days: int = Query(30, ge=1, le=90),
) -> dict[str, Any]:
    """Return aggregate timeline stats for generation history."""
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)
    start_iso = start_date.isoformat()
    end_iso = today.isoformat()

    async with get_db() as db:
        daily_cursor = await db.execute(
            """
            SELECT
                strftime('%Y-%m-%d', created_at) AS date,
                COUNT(*) AS count,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                AVG(
                    CASE
                        WHEN status = 'completed' AND generation_time_sec IS NOT NULL
                        THEN generation_time_sec
                    END
                ) AS avg_generation_time_sec
            FROM generations
            WHERE date(created_at) BETWEEN date(?) AND date(?)
            GROUP BY date
            ORDER BY date ASC
            """,
            (start_iso, end_iso),
        )
        daily_rows = await daily_cursor.fetchall()

        checkpoint_daily_cursor = await db.execute(
            """
            SELECT
                strftime('%Y-%m-%d', created_at) AS date,
                checkpoint,
                COUNT(*) AS count
            FROM generations
            WHERE status = 'completed'
              AND date(created_at) BETWEEN date(?) AND date(?)
            GROUP BY date, checkpoint
            ORDER BY date ASC
            """,
            (start_iso, end_iso),
        )
        checkpoint_daily_rows = await checkpoint_daily_cursor.fetchall()

        checkpoint_cursor = await db.execute(
            """
            SELECT checkpoint, COUNT(*) AS count
            FROM generations
            WHERE status = 'completed'
              AND date(created_at) BETWEEN date(?) AND date(?)
            GROUP BY checkpoint
            ORDER BY count DESC, checkpoint ASC
            """,
            (start_iso, end_iso),
        )
        checkpoint_rows = await checkpoint_cursor.fetchall()

        hour_cursor = await db.execute(
            """
            SELECT CAST(strftime('%H', created_at) AS INTEGER) AS hour, COUNT(*) AS count
            FROM generations
            WHERE date(created_at) BETWEEN date(?) AND date(?)
            GROUP BY hour
            ORDER BY hour ASC
            """,
            (start_iso, end_iso),
        )
        hour_rows = await hour_cursor.fetchall()

        streak_cursor = await db.execute(
            """
            SELECT DISTINCT strftime('%Y-%m-%d', created_at) AS date
            FROM generations
            ORDER BY date ASC
            """
        )
        streak_rows = await streak_cursor.fetchall()

    date_keys = [
        (start_date + timedelta(days=offset)).isoformat()
        for offset in range(days)
    ]
    daily_map: dict[str, dict[str, Any]] = {
        key: {
            "date": key,
            "count": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "checkpoints": {},
            "avg_generation_time_sec": None,
        }
        for key in date_keys
    }

    for row in daily_rows:
        date_key = row.get("date")
        if not date_key or date_key not in daily_map:
            continue
        avg_time = row.get("avg_generation_time_sec")
        daily_map[date_key].update(
            {
                "count": int(row.get("count") or 0),
                "completed": int(row.get("completed") or 0),
                "failed": int(row.get("failed") or 0),
                "cancelled": int(row.get("cancelled") or 0),
                "avg_generation_time_sec": (
                    round(float(avg_time), 2) if avg_time is not None else None
                ),
            }
        )

    for row in checkpoint_daily_rows:
        date_key = row.get("date")
        checkpoint = row.get("checkpoint")
        if not date_key or date_key not in daily_map or not checkpoint:
            continue
        daily_map[date_key]["checkpoints"][checkpoint] = int(row.get("count") or 0)

    daily = [daily_map[key] for key in date_keys]
    total = sum(item["count"] for item in daily)

    total_completed = sum(int(row.get("count") or 0) for row in checkpoint_rows)
    by_checkpoint = [
        {
            "checkpoint": row["checkpoint"],
            "count": int(row.get("count") or 0),
            "pct": round(
                (int(row.get("count") or 0) / total_completed) * 100,
                1,
            )
            if total_completed > 0
            else 0.0,
        }
        for row in checkpoint_rows
    ]

    by_hour_map = {hour: 0 for hour in range(24)}
    for row in hour_rows:
        hour = row.get("hour")
        if hour is None:
            continue
        by_hour_map[int(hour)] = int(row.get("count") or 0)
    by_hour = [{"hour": hour, "count": by_hour_map[hour]} for hour in range(24)]

    streak_dates = [row.get("date") for row in streak_rows if row.get("date")]
    streak = _calculate_streak(streak_dates, today)

    return {
        "days": days,
        "total": total,
        "daily": daily,
        "by_checkpoint": by_checkpoint,
        "by_hour": by_hour,
        "streak": streak,
    }


@router.get("", response_model=PaginatedResponse)
async def list_gallery(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    checkpoint: Optional[str] = None,
    tags: Optional[str] = Query(None, description="Comma-separated tag list"),
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    favorites: bool = Query(False),
    sort_by: str = "created_at",
    sort_order: str = "desc",
    publish_approved: Optional[int] = Query(
        None,
        description="Filter by publish_approved status: 0=pending, 1=approved, 2=rejected",
    ),
    min_quality: Optional[int] = Query(None, description="Minimum quality_score filter"),
    max_quality: Optional[int] = Query(None, description="Maximum quality_score filter"),
) -> PaginatedResponse:
    """Browse completed generations with filtering and pagination."""
    allowed_sort = {"created_at", "generation_time_sec", "seed", "checkpoint", "quality_score", "quality_ai_score"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    if sort_order.lower() not in ("asc", "desc"):
        sort_order = "desc"

    conditions: List[str] = ["status = 'completed'"]
    params: List[Any] = []

    if checkpoint:
        conditions.append("checkpoint = ?")
        params.append(checkpoint)
    if search:
        conditions.append("(prompt LIKE ? OR notes LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])
    if date_from:
        conditions.append("created_at >= ?")
        params.append(date_from)
    if date_to:
        if len(date_to) == 10:  # YYYY-MM-DD
            date_to = f"{date_to}T23:59:59.999999+00:00"
        conditions.append("created_at <= ?")
        params.append(date_to)
    if tags:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                conditions.append("tags LIKE ?")
                params.append(f'%"{tag}"%')
    if favorites:
        conditions.append("is_favorite = 1")
    if publish_approved is not None:
        conditions.append("publish_approved = ?")
        params.append(publish_approved)
    if min_quality is not None:
        conditions.append("quality_score >= ?")
        params.append(min_quality)
    if max_quality is not None:
        conditions.append("quality_score <= ?")
        params.append(max_quality)

    where = " AND ".join(conditions)

    async with get_db() as db:
        # Total count
        count_cursor = await db.execute(
            f"SELECT COUNT(*) AS cnt FROM generations WHERE {where}", params
        )
        count_row = await count_cursor.fetchone()
        total = count_row["cnt"] if count_row else 0

        total_pages = max(1, math.ceil(total / per_page))
        offset = (page - 1) * per_page

        cursor = await db.execute(
            f"SELECT * FROM generations WHERE {where} "
            f"ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?",
            [*params, per_page, offset],
        )
        rows = await cursor.fetchall()

    items = [_row_to_response(r) for r in rows]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.delete("/{generation_id}")
async def delete_generation(generation_id: str) -> dict:
    """Delete a generation record and its associated files."""
    from app.config import settings

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, image_path, watermarked_path, upscaled_image_path, adetailed_path, hiresfix_path, thumbnail_path, workflow_path "
            "FROM generations WHERE id = ?",
            (generation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation {generation_id} not found",
            )

        # Delete files
        for field in (
            "image_path",
            "watermarked_path",
            "upscaled_image_path",
            "adetailed_path",
            "hiresfix_path",
            "thumbnail_path",
            "workflow_path",
        ):
            rel = row.get(field)
            if rel:
                full = _resolve_public_file(settings.DATA_DIR, rel)
                if full and full.exists() and full.is_file():
                    full.unlink(missing_ok=True)

        await db.execute(
            "DELETE FROM generations WHERE id = ?", (generation_id,)
        )
        await db.commit()

    return {"success": True}
