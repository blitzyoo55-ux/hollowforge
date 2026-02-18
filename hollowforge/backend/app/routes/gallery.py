"""Gallery browsing and deletion endpoints."""

import json
import math
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
        upscaled_image_path=row.get("upscaled_image_path"),
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
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
    )


@router.get("", response_model=PaginatedResponse)
async def list_gallery(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    checkpoint: Optional[str] = None,
    tags: Optional[str] = Query(None, description="Comma-separated tag list"),
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> PaginatedResponse:
    """Browse completed generations with filtering and pagination."""
    allowed_sort = {"created_at", "generation_time_sec", "seed", "checkpoint"}
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
            "SELECT id, image_path, upscaled_image_path, thumbnail_path, workflow_path "
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
        for field in ("image_path", "upscaled_image_path", "thumbnail_path", "workflow_path"):
            rel = row.get(field)
            if rel:
                full = settings.DATA_DIR / rel
                if full.exists():
                    full.unlink(missing_ok=True)

        await db.execute(
            "DELETE FROM generations WHERE id = ?", (generation_id,)
        )
        await db.commit()

    return {"success": True}
