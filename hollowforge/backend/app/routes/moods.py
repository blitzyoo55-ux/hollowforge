"""Mood mapping CRUD endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite
from fastapi import APIRouter, HTTPException, status

from app.db import get_db
from app.models import MoodMappingCreate, MoodMappingResponse, MoodMappingUpdate

router = APIRouter(prefix="/api/v1/moods", tags=["moods"])


def _parse_json(val: str | None, default: Any = None) -> Any:
    if val is None:
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def _normalize_mood_keyword(value: str) -> str:
    return value.strip().lower()


def _normalize_lora_ids(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


async def _validate_lora_ids(db: aiosqlite.Connection, lora_ids: list[str]) -> None:
    if not lora_ids:
        return
    placeholders = ",".join("?" for _ in lora_ids)
    cursor = await db.execute(
        f"SELECT id FROM lora_profiles WHERE id IN ({placeholders})",
        lora_ids,
    )
    rows = await cursor.fetchall()
    existing = {str(row["id"]) for row in rows}
    missing = [lora_id for lora_id in lora_ids if lora_id not in existing]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown LoRA id(s): {', '.join(missing)}",
        )


async def _uses_integer_mood_id(db: aiosqlite.Connection) -> bool:
    cursor = await db.execute("PRAGMA table_info(mood_mappings)")
    rows = await cursor.fetchall()
    for row in rows:
        if row.get("name") != "id":
            continue
        col_type = str(row.get("type") or "").upper()
        return "INT" in col_type
    return False


def _row_to_response(row: dict[str, Any]) -> MoodMappingResponse:
    parsed = _parse_json(row.get("lora_ids"), [])
    lora_ids = [str(item) for item in parsed if isinstance(item, (str, int))]
    return MoodMappingResponse(
        id=str(row["id"]),
        mood_keyword=row["mood_keyword"],
        lora_ids=lora_ids,
        prompt_additions=row.get("prompt_additions") or "",
        created_at=row["created_at"],
    )


@router.get("", response_model=list[MoodMappingResponse])
async def list_moods() -> list[MoodMappingResponse]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM mood_mappings ORDER BY mood_keyword ASC")
        rows = await cursor.fetchall()
    return [_row_to_response(row) for row in rows]


@router.post("", response_model=MoodMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mood(payload: MoodMappingCreate) -> MoodMappingResponse:
    mood_keyword = _normalize_mood_keyword(payload.mood_keyword)
    if not mood_keyword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mood_keyword cannot be empty",
        )
    lora_ids = _normalize_lora_ids(payload.lora_ids)
    prompt_additions = payload.prompt_additions or ""
    now = datetime.now(timezone.utc).isoformat()

    async with get_db() as db:
        await _validate_lora_ids(db, lora_ids)
        mood_id_is_integer = await _uses_integer_mood_id(db)

        try:
            if mood_id_is_integer:
                await db.execute(
                    """
                    INSERT INTO mood_mappings
                    (mood_keyword, lora_ids, prompt_additions, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (mood_keyword, json.dumps(lora_ids), prompt_additions, now),
                )
            else:
                await db.execute(
                    """
                    INSERT INTO mood_mappings
                    (id, mood_keyword, lora_ids, prompt_additions, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        f"mood_{uuid.uuid4().hex}",
                        mood_keyword,
                        json.dumps(lora_ids),
                        prompt_additions,
                        now,
                    ),
                )
            await db.commit()
        except aiosqlite.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mood keyword '{mood_keyword}' already exists",
            ) from exc

        cursor = await db.execute(
            "SELECT * FROM mood_mappings WHERE mood_keyword = ?",
            (mood_keyword,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load created mood mapping",
        )
    return _row_to_response(row)


@router.get("/{mood_id}", response_model=MoodMappingResponse)
async def get_mood(mood_id: str) -> MoodMappingResponse:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM mood_mappings WHERE id = ?", (mood_id,))
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mood mapping {mood_id} not found",
        )
    return _row_to_response(row)


@router.put("/{mood_id}", response_model=MoodMappingResponse)
async def update_mood(mood_id: str, payload: MoodMappingUpdate) -> MoodMappingResponse:
    updates_in = payload.model_dump(exclude_unset=True)
    updates: dict[str, Any] = {}

    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM mood_mappings WHERE id = ?", (mood_id,))
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mood mapping {mood_id} not found",
            )

        if "mood_keyword" in updates_in:
            mood_keyword = _normalize_mood_keyword(str(updates_in["mood_keyword"]))
            if not mood_keyword:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="mood_keyword cannot be empty",
                )
            updates["mood_keyword"] = mood_keyword
        if "lora_ids" in updates_in:
            normalized_ids = _normalize_lora_ids(updates_in["lora_ids"] or [])
            await _validate_lora_ids(db, normalized_ids)
            updates["lora_ids"] = json.dumps(normalized_ids)
        if "prompt_additions" in updates_in:
            updates["prompt_additions"] = updates_in["prompt_additions"] or ""

        if updates:
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            values = list(updates.values()) + [mood_id]
            try:
                await db.execute(
                    f"UPDATE mood_mappings SET {set_clause} WHERE id = ?",
                    values,
                )
                await db.commit()
            except aiosqlite.IntegrityError as exc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Mood keyword '{updates.get('mood_keyword')}' already exists",
                ) from exc

        cursor = await db.execute("SELECT * FROM mood_mappings WHERE id = ?", (mood_id,))
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load updated mood mapping",
        )
    return _row_to_response(row)


@router.delete("/{mood_id}")
async def delete_mood(mood_id: str) -> dict[str, bool]:
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM mood_mappings WHERE id = ?", (mood_id,))
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mood mapping {mood_id} not found",
            )
        await db.execute("DELETE FROM mood_mappings WHERE id = ?", (mood_id,))
        await db.commit()
    return {"success": True}
