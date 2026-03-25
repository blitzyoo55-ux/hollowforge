"""Curation queue and direction board endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.db import get_db
from app.services.quality_service import APPROVE_THRESHOLD, auto_approve, update_quality_scores

router = APIRouter(tags=["curation"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CurationItem(BaseModel):
    id: str
    prompt: str
    checkpoint: str
    quality_score: Optional[int] = None
    publish_approved: int = 0
    curated_at: Optional[str] = None
    direction_pinned: int = 0
    image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    upscaled_image_path: Optional[str] = None
    upscaled_preview_path: Optional[str] = None
    adetailed_path: Optional[str] = None
    hiresfix_path: Optional[str] = None
    is_favorite: bool = False
    steps: int
    width: int
    height: int
    created_at: str
    completed_at: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None


class DirectionReferenceCreate(BaseModel):
    external_url: Optional[str] = None
    generation_id: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    source: str = "external"


class DirectionReferenceResponse(BaseModel):
    id: str
    external_url: Optional[str] = None
    generation_id: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    source: str
    created_at: str


class AutoApproveResponse(BaseModel):
    approved: int
    threshold: int


class RecalculateResponse(BaseModel):
    updated: int


class ReadyToggleResponse(BaseModel):
    id: str
    publish_approved: int
    curated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_json(val: Optional[str], default: Any = None) -> Any:
    if val is None:
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def _row_to_curation_item(row: dict) -> CurationItem:
    return CurationItem(
        id=row["id"],
        prompt=row["prompt"],
        checkpoint=row["checkpoint"],
        quality_score=row.get("quality_score"),
        publish_approved=row.get("publish_approved", 0),
        curated_at=row.get("curated_at"),
        direction_pinned=row.get("direction_pinned", 0),
        image_path=row.get("image_path"),
        thumbnail_path=row.get("thumbnail_path"),
        upscaled_image_path=row.get("upscaled_image_path"),
        upscaled_preview_path=row.get("upscaled_preview_path"),
        adetailed_path=row.get("adetailed_path"),
        hiresfix_path=row.get("hiresfix_path"),
        is_favorite=bool(row.get("is_favorite", 0)),
        steps=row["steps"],
        width=row["width"],
        height=row["height"],
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
        tags=_parse_json(row.get("tags")),
        notes=row.get("notes"),
    )


def _row_to_direction_ref(row: dict) -> DirectionReferenceResponse:
    return DirectionReferenceResponse(
        id=row["id"],
        external_url=row.get("external_url"),
        generation_id=row.get("generation_id"),
        title=row.get("title"),
        notes=row.get("notes"),
        tags=_parse_json(row.get("tags")),
        source=row.get("source", "external"),
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Curation queue endpoints
# ---------------------------------------------------------------------------


@router.get("/api/v1/curation/queue", response_model=List[CurationItem])
async def get_curation_queue(
    limit: int = Query(50, ge=1, le=200),
) -> List[CurationItem]:
    """Return generations pending curation (publish_approved=0, quality_score scored),
    sorted by quality_score descending."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, prompt, checkpoint, quality_score, publish_approved, curated_at,
                      direction_pinned, image_path, thumbnail_path, upscaled_image_path,
                      adetailed_path, hiresfix_path, is_favorite, steps, width, height,
                      created_at, completed_at, tags, notes
               FROM generations
               WHERE status = 'completed'
                 AND publish_approved = 0
                 AND quality_score IS NOT NULL
               ORDER BY quality_score DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
    return [_row_to_curation_item(r) for r in rows]


@router.post("/api/v1/curation/{generation_id}/approve")
async def approve_generation(generation_id: str) -> dict:
    """Approve a generation for publishing (publish_approved=1)."""
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM generations WHERE id = ?", (generation_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation {generation_id} not found",
            )
        await db.execute(
            "UPDATE generations SET publish_approved = 1, curated_at = ? WHERE id = ?",
            (now, generation_id),
        )
        await db.commit()
    return {"success": True, "publish_approved": 1, "curated_at": now}


@router.post("/api/v1/curation/{generation_id}/toggle-ready", response_model=ReadyToggleResponse)
async def toggle_ready_generation(generation_id: str) -> ReadyToggleResponse:
    """Toggle a generation between pending (0) and ready-to-go (1)."""
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, publish_approved FROM generations WHERE id = ?",
            (generation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation {generation_id} not found",
            )

        current = int(row.get("publish_approved") or 0)
        next_value = 0 if current == 1 else 1
        curated_at = now if next_value == 1 else None

        await db.execute(
            "UPDATE generations SET publish_approved = ?, curated_at = ? WHERE id = ?",
            (next_value, curated_at, generation_id),
        )
        await db.commit()

    return ReadyToggleResponse(
        id=generation_id,
        publish_approved=next_value,
        curated_at=curated_at,
    )


@router.post("/api/v1/curation/{generation_id}/reject")
async def reject_generation(generation_id: str) -> dict:
    """Reject a generation from publishing (publish_approved=2)."""
    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM generations WHERE id = ?", (generation_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation {generation_id} not found",
            )
        await db.execute(
            "UPDATE generations SET publish_approved = 2, curated_at = ? WHERE id = ?",
            (now, generation_id),
        )
        await db.commit()
    return {"success": True, "publish_approved": 2, "curated_at": now}


@router.get("/api/v1/curation/approved", response_model=List[CurationItem])
async def get_approved(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[CurationItem]:
    """Return all approved content ready to publish (publish_approved=1)."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, prompt, checkpoint, quality_score, publish_approved, curated_at,
                      direction_pinned, image_path, thumbnail_path, upscaled_image_path,
                      adetailed_path, hiresfix_path, is_favorite, steps, width, height,
                      created_at, completed_at, tags, notes
               FROM generations
               WHERE status = 'completed'
                 AND publish_approved = 1
               ORDER BY curated_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        rows = await cursor.fetchall()
    return [_row_to_curation_item(r) for r in rows]


@router.post("/api/v1/curation/auto-approve", response_model=AutoApproveResponse)
async def run_auto_approve(
    threshold: int = Query(APPROVE_THRESHOLD, ge=0, le=100),
) -> AutoApproveResponse:
    """Auto-approve all pending generations with quality_score >= threshold."""
    async with get_db() as db:
        approved = await auto_approve(db, threshold=threshold)
    return AutoApproveResponse(approved=approved, threshold=threshold)


@router.post("/api/v1/curation/recalculate", response_model=RecalculateResponse)
async def recalculate_scores(
    limit: int = Query(500, ge=1, le=5000),
) -> RecalculateResponse:
    """Recalculate quality scores for the most recent `limit` completed generations."""
    async with get_db() as db:
        updated = await update_quality_scores(db, limit=limit)
    return RecalculateResponse(updated=updated)


# ---------------------------------------------------------------------------
# Direction board endpoints
# ---------------------------------------------------------------------------


@router.get("/api/v1/direction/references", response_model=List[DirectionReferenceResponse])
async def list_direction_references() -> List[DirectionReferenceResponse]:
    """List all direction board references."""
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT id, external_url, generation_id, title, notes, tags, source, created_at
               FROM direction_references
               ORDER BY created_at DESC"""
        )
        rows = await cursor.fetchall()
    return [_row_to_direction_ref(r) for r in rows]


@router.post(
    "/api/v1/direction/references",
    response_model=DirectionReferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_direction_reference(
    payload: DirectionReferenceCreate,
) -> DirectionReferenceResponse:
    """Add a new direction board reference (external URL or internal generation)."""
    if not payload.external_url and not payload.generation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either external_url or generation_id must be provided",
        )

    ref_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    tags_json = json.dumps(payload.tags) if payload.tags else None

    async with get_db() as db:
        # If linking to an internal generation, verify it exists
        if payload.generation_id:
            cursor = await db.execute(
                "SELECT id FROM generations WHERE id = ?", (payload.generation_id,)
            )
            if await cursor.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Generation {payload.generation_id} not found",
                )

        await db.execute(
            """INSERT INTO direction_references
               (id, external_url, generation_id, title, notes, tags, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ref_id,
                payload.external_url,
                payload.generation_id,
                payload.title,
                payload.notes,
                tags_json,
                payload.source,
                now,
            ),
        )
        await db.commit()

    return DirectionReferenceResponse(
        id=ref_id,
        external_url=payload.external_url,
        generation_id=payload.generation_id,
        title=payload.title,
        notes=payload.notes,
        tags=payload.tags,
        source=payload.source,
        created_at=now,
    )


@router.delete("/api/v1/direction/references/{reference_id}")
async def delete_direction_reference(reference_id: str) -> dict:
    """Delete a direction board reference by ID."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM direction_references WHERE id = ?", (reference_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reference {reference_id} not found",
            )
        await db.execute(
            "DELETE FROM direction_references WHERE id = ?", (reference_id,)
        )
        await db.commit()
    return {"success": True}


@router.post("/api/v1/direction/pin/{generation_id}")
async def pin_to_direction_board(generation_id: str) -> dict:
    """Pin an internal generation to the direction board (direction_pinned=1)."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, direction_pinned FROM generations WHERE id = ?", (generation_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Generation {generation_id} not found",
            )
        new_val = 0 if row.get("direction_pinned", 0) else 1
        await db.execute(
            "UPDATE generations SET direction_pinned = ? WHERE id = ?",
            (new_val, generation_id),
        )
        await db.commit()
    return {"success": True, "direction_pinned": new_val}
