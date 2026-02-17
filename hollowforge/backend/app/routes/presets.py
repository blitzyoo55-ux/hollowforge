"""Preset CRUD endpoints."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from app.db import get_db
from app.models import LoraInput, PresetCreate, PresetResponse, PresetUpdate

router = APIRouter(prefix="/api/v1/presets", tags=["presets"])


def _parse_json(val: Optional[str], default: Any = None) -> Any:
    if val is None:
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


def _row_to_response(row: dict) -> PresetResponse:
    loras_raw = _parse_json(row.get("loras"), [])
    loras = [LoraInput(**l) if isinstance(l, dict) else l for l in loras_raw]
    return PresetResponse(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        checkpoint=row["checkpoint"],
        loras=loras,
        prompt_template=row.get("prompt_template"),
        negative_prompt=row.get("negative_prompt"),
        default_params=_parse_json(row.get("default_params"), {}),
        tags=_parse_json(row.get("tags")),
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("", response_model=List[PresetResponse])
async def list_presets() -> List[PresetResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM presets ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
    return [_row_to_response(r) for r in rows]


@router.post(
    "", response_model=PresetResponse, status_code=status.HTTP_201_CREATED
)
async def create_preset(preset: PresetCreate) -> PresetResponse:
    preset_id = str(uuid.uuid4())
    now = _now_iso()
    loras_json = json.dumps([l.model_dump() for l in preset.loras])
    tags_json = json.dumps(preset.tags) if preset.tags else None
    params_json = json.dumps(preset.default_params)

    async with get_db() as db:
        await db.execute(
            """INSERT INTO presets
               (id, name, description, checkpoint, loras, prompt_template,
                negative_prompt, default_params, tags, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                preset_id, preset.name, preset.description, preset.checkpoint,
                loras_json, preset.prompt_template, preset.negative_prompt,
                params_json, tags_json, now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM presets WHERE id = ?", (preset_id,)
        )
        row = await cursor.fetchone()
    return _row_to_response(row)


@router.get("/{preset_id}", response_model=PresetResponse)
async def get_preset(preset_id: str) -> PresetResponse:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM presets WHERE id = ?", (preset_id,)
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preset {preset_id} not found",
        )
    return _row_to_response(row)


@router.put("/{preset_id}", response_model=PresetResponse)
async def update_preset(preset_id: str, update: PresetUpdate) -> PresetResponse:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM presets WHERE id = ?", (preset_id,)
        )
        existing = await cursor.fetchone()
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preset {preset_id} not found",
            )

        updates: Dict[str, Any] = {}
        if update.name is not None:
            updates["name"] = update.name
        if update.description is not None:
            updates["description"] = update.description
        if update.checkpoint is not None:
            updates["checkpoint"] = update.checkpoint
        if update.loras is not None:
            updates["loras"] = json.dumps([l.model_dump() for l in update.loras])
        if update.prompt_template is not None:
            updates["prompt_template"] = update.prompt_template
        if update.negative_prompt is not None:
            updates["negative_prompt"] = update.negative_prompt
        if update.default_params is not None:
            updates["default_params"] = json.dumps(update.default_params)
        if update.tags is not None:
            updates["tags"] = json.dumps(update.tags)

        if updates:
            updates["updated_at"] = _now_iso()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [preset_id]
            await db.execute(
                f"UPDATE presets SET {set_clause} WHERE id = ?", values
            )
            await db.commit()

        cursor = await db.execute(
            "SELECT * FROM presets WHERE id = ?", (preset_id,)
        )
        row = await cursor.fetchone()
    return _row_to_response(row)


@router.delete("/{preset_id}")
async def delete_preset(preset_id: str) -> dict:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM presets WHERE id = ?", (preset_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Preset {preset_id} not found",
            )
        await db.execute("DELETE FROM presets WHERE id = ?", (preset_id,))
        await db.commit()
    return {"success": True}
