"""Collection management endpoints."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite
from fastapi import APIRouter, HTTPException, Query, status

from app.db import get_db
from app.models import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionItemRequest,
    CollectionResponse,
    CollectionUpdate,
    GalleryItem,
    LoraInput,
)

router = APIRouter(prefix="/api/v1/collections", tags=["collections"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(value: Optional[str], default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _collection_select_sql(
    include_contains_generation: bool,
    where_clause: str = "",
) -> str:
    contains_expr = (
        """EXISTS(
               SELECT 1
               FROM collection_items ci2
               WHERE ci2.collection_id = c.id AND ci2.generation_id = ?
           ) AS contains_generation"""
        if include_contains_generation
        else "0 AS contains_generation"
    )

    return f"""
        SELECT
            c.id,
            c.name,
            c.description,
            c.cover_image_id,
            c.created_at,
            c.updated_at,
            COALESCE(stats.image_count, 0) AS image_count,
            COALESCE(cover.thumbnail_path, fallback.thumbnail_path) AS cover_thumbnail_path,
            {contains_expr}
        FROM collections c
        LEFT JOIN (
            SELECT collection_id, COUNT(*) AS image_count
            FROM collection_items
            GROUP BY collection_id
        ) AS stats ON stats.collection_id = c.id
        LEFT JOIN generations cover ON cover.id = c.cover_image_id
        LEFT JOIN generations fallback ON fallback.id = (
            SELECT ci3.generation_id
            FROM collection_items ci3
            WHERE ci3.collection_id = c.id
            ORDER BY ci3.added_at DESC
            LIMIT 1
        )
        {where_clause}
        ORDER BY c.created_at DESC
    """


def _row_to_collection(row: dict[str, Any]) -> CollectionResponse:
    return CollectionResponse(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        cover_image_id=row.get("cover_image_id"),
        cover_thumbnail_path=row.get("cover_thumbnail_path"),
        image_count=int(row.get("image_count", 0) or 0),
        contains_generation=bool(row.get("contains_generation", 0)),
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
    )


def _row_to_gallery_item(row: dict[str, Any]) -> GalleryItem:
    loras_raw = _parse_json(row.get("loras"), [])
    loras = [LoraInput(**l) if isinstance(l, dict) else l for l in loras_raw]
    return GalleryItem(
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
    )


async def _fetch_collection_row(
    db: aiosqlite.Connection,
    collection_id: str,
    generation_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    if generation_id:
        query = _collection_select_sql(True, "WHERE c.id = ?")
        cursor = await db.execute(query, (generation_id, collection_id))
    else:
        query = _collection_select_sql(False, "WHERE c.id = ?")
        cursor = await db.execute(query, (collection_id,))
    return await cursor.fetchone()


@router.get("", response_model=list[CollectionResponse])
async def list_collections(
    generation_id: Optional[str] = Query(
        default=None,
        description="Optional generation id to mark membership in each collection",
    ),
) -> list[CollectionResponse]:
    """Return all collections with image counts and cover thumbnail."""
    async with get_db() as db:
        if generation_id:
            query = _collection_select_sql(True)
            cursor = await db.execute(query, (generation_id,))
        else:
            query = _collection_select_sql(False)
            cursor = await db.execute(query)
        rows = await cursor.fetchall()

    return [_row_to_collection(row) for row in rows]


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED)
async def create_collection(payload: CollectionCreate) -> CollectionResponse:
    """Create a new collection."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Collection name cannot be empty",
        )

    description = payload.description.strip() if payload.description else None
    collection_id = str(uuid.uuid4())
    now = _now_iso()

    async with get_db() as db:
        try:
            await db.execute(
                """INSERT INTO collections (id, name, description, created_at, updated_at)
                   VALUES (?, ?, ?, ?, NULL)""",
                (collection_id, name, description, now),
            )
            await db.commit()
        except aiosqlite.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Collection name already exists",
            ) from exc

        row = await _fetch_collection_row(db, collection_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load created collection",
        )
    return _row_to_collection(row)


@router.get("/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
) -> CollectionDetailResponse:
    """Return collection metadata and paginated images."""
    async with get_db() as db:
        collection_row = await _fetch_collection_row(db, collection_id)
        if collection_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection {collection_id} not found",
            )

        count_cursor = await db.execute(
            "SELECT COUNT(*) AS cnt FROM collection_items WHERE collection_id = ?",
            (collection_id,),
        )
        count_row = await count_cursor.fetchone()
        total = int(count_row["cnt"]) if count_row else 0

        total_pages = max(1, math.ceil(total / per_page))
        offset = (page - 1) * per_page

        cursor = await db.execute(
            """SELECT g.*
               FROM collection_items ci
               JOIN generations g ON g.id = ci.generation_id
               WHERE ci.collection_id = ?
               ORDER BY ci.added_at DESC
               LIMIT ? OFFSET ?""",
            (collection_id, per_page, offset),
        )
        rows = await cursor.fetchall()

    return CollectionDetailResponse(
        collection=_row_to_collection(collection_row),
        items=[_row_to_gallery_item(row) for row in rows],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    payload: CollectionUpdate,
) -> CollectionResponse:
    """Update collection metadata and optional cover image."""
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update fields provided",
        )

    if "name" in updates and updates["name"] is not None:
        name = str(updates["name"]).strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Collection name cannot be empty",
            )
        updates["name"] = name

    if "cover_image_id" in updates and isinstance(updates["cover_image_id"], str):
        cover_value = updates["cover_image_id"].strip()
        updates["cover_image_id"] = cover_value or None

    now = _now_iso()

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM collections WHERE id = ?",
            (collection_id,),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection {collection_id} not found",
            )

        cover_image_id = updates.get("cover_image_id")
        if cover_image_id is not None:
            cursor = await db.execute(
                """SELECT 1 FROM collection_items
                   WHERE collection_id = ? AND generation_id = ?""",
                (collection_id, cover_image_id),
            )
            if await cursor.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="cover_image_id must be an item in this collection",
                )

        set_clauses: list[str] = []
        params: list[Any] = []
        for key in ("name", "description", "cover_image_id"):
            if key in updates:
                set_clauses.append(f"{key} = ?")
                params.append(updates[key])

        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(collection_id)

        try:
            await db.execute(
                f"UPDATE collections SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )
            await db.commit()
        except aiosqlite.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Collection name already exists",
            ) from exc

        updated = await _fetch_collection_row(db, collection_id)

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection {collection_id} not found",
        )
    return _row_to_collection(updated)


@router.delete("/{collection_id}")
async def delete_collection(collection_id: str) -> dict[str, bool]:
    """Delete a collection and cascade-delete its items."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM collections WHERE id = ?",
            (collection_id,),
        )
        await db.commit()

    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection {collection_id} not found",
        )

    return {"success": True}


@router.post("/{collection_id}/items")
async def add_collection_item(
    collection_id: str,
    payload: CollectionItemRequest,
) -> dict[str, bool]:
    """Add a generation to a collection."""
    generation_id = payload.generation_id.strip()
    if not generation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="generation_id cannot be empty",
        )

    now = _now_iso()

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT cover_image_id FROM collections WHERE id = ?",
            (collection_id,),
        )
        collection_row = await cursor.fetchone()
        if collection_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection {collection_id} not found",
            )

        cursor = await db.execute(
            "SELECT id FROM generations WHERE id = ?",
            (generation_id,),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation {generation_id} not found",
            )

        cursor = await db.execute(
            """SELECT 1 FROM collection_items
               WHERE collection_id = ? AND generation_id = ?""",
            (collection_id, generation_id),
        )
        already_exists = await cursor.fetchone() is not None

        if not already_exists:
            await db.execute(
                """INSERT INTO collection_items (collection_id, generation_id, added_at)
                   VALUES (?, ?, ?)""",
                (collection_id, generation_id, now),
            )

        if collection_row.get("cover_image_id") is None:
            await db.execute(
                """UPDATE collections
                   SET cover_image_id = ?, updated_at = ?
                   WHERE id = ?""",
                (generation_id, now, collection_id),
            )
        else:
            await db.execute(
                "UPDATE collections SET updated_at = ? WHERE id = ?",
                (now, collection_id),
            )

        await db.commit()

    return {"success": True}


@router.delete("/{collection_id}/items/{generation_id}")
async def remove_collection_item(
    collection_id: str,
    generation_id: str,
) -> dict[str, bool]:
    """Remove a generation from a collection."""
    now = _now_iso()

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT cover_image_id FROM collections WHERE id = ?",
            (collection_id,),
        )
        collection_row = await cursor.fetchone()
        if collection_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection {collection_id} not found",
            )

        cursor = await db.execute(
            """SELECT 1 FROM collection_items
               WHERE collection_id = ? AND generation_id = ?""",
            (collection_id, generation_id),
        )
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collection item not found",
            )

        await db.execute(
            """DELETE FROM collection_items
               WHERE collection_id = ? AND generation_id = ?""",
            (collection_id, generation_id),
        )

        if collection_row.get("cover_image_id") == generation_id:
            fallback_cursor = await db.execute(
                """SELECT generation_id
                   FROM collection_items
                   WHERE collection_id = ?
                   ORDER BY added_at DESC
                   LIMIT 1""",
                (collection_id,),
            )
            fallback = await fallback_cursor.fetchone()
            fallback_id = fallback["generation_id"] if fallback else None
            await db.execute(
                """UPDATE collections
                   SET cover_image_id = ?, updated_at = ?
                   WHERE id = ?""",
                (fallback_id, now, collection_id),
            )
        else:
            await db.execute(
                "UPDATE collections SET updated_at = ? WHERE id = ?",
                (now, collection_id),
            )

        await db.commit()

    return {"success": True}
