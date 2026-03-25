"""Bulk export: select images -> watermark + platform resize -> zip download."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from PIL import Image, ImageOps

from app.config import settings
from app.db import get_db
from app.models import ExportRequest
from app.services import watermark_service

router = APIRouter(prefix="/api/v1/export", tags=["export"])
logger = logging.getLogger(__name__)

PLATFORM_SPECS = {
    "fanbox": {"max_long_edge": 1200, "format": "JPEG", "quality": 92},
    "fansly": {"max_long_edge": 1080, "format": "JPEG", "quality": 92},
    "twitter": {"max_long_edge": 1280, "format": "JPEG", "quality": 90},
    "pixiv": {"max_long_edge": 2048, "format": "JPEG", "quality": 95},
    "custom": {"max_long_edge": None, "format": "JPEG", "quality": 92},
}

_DEFAULT_WATERMARK_SETTINGS: dict[str, Any] = {
    "enabled": False,
    "text": "Lab-XX",
    "position": "bottom-right",
    "opacity": 0.6,
    "font_size": 36,
    "padding": 20,
    "color": "#FFFFFF",
}

METADATA_EXPORT_FIELDS = [
    "id",
    "checkpoint",
    "loras",
    "prompt",
    "negative_prompt",
    "seed",
    "steps",
    "cfg",
    "sampler",
    "scheduler",
    "width",
    "height",
    "status",
    "created_at",
    "image_path",
    "upscaled_image_path",
    "adetailed_path",
    "hiresfix_path",
    "tags",
    "notes",
]


def _resolve_generation_source_path(rel_path: str | None) -> Path | None:
    if not rel_path:
        return None

    rel = Path(rel_path)
    if rel.is_absolute() or not rel.parts:
        return None

    full_path = (settings.DATA_DIR / rel).resolve()
    try:
        full_path.relative_to(settings.DATA_DIR.resolve())
    except ValueError:
        return None
    return full_path


def _resize_for_platform(image: Image.Image, max_long_edge: int | None) -> Image.Image:
    normalized = ImageOps.exif_transpose(image)
    if max_long_edge is None:
        return normalized.copy()

    width, height = normalized.size
    long_edge = max(width, height)
    if long_edge <= max_long_edge:
        return normalized.copy()

    ratio = max_long_edge / float(long_edge)
    new_size = (
        max(1, int(round(width * ratio))),
        max(1, int(round(height * ratio))),
    )
    return normalized.resize(new_size, Image.LANCZOS)


def _resolve_watermark_output_path(raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (settings.DATA_DIR / candidate).resolve()


def _apply_watermark_with_service(
    image: Image.Image, watermark_settings: dict[str, Any]
) -> Image.Image:
    temp_input_path: Path | None = None
    temp_output_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_input_path = Path(temp_file.name)

        image.convert("RGBA").save(temp_input_path, format="PNG")
        output_path = watermark_service.apply_watermark(
            str(temp_input_path), watermark_settings
        )
        temp_output_path = _resolve_watermark_output_path(output_path)

        with Image.open(temp_output_path) as watermarked:
            return watermarked.copy()
    finally:
        if temp_input_path is not None:
            temp_input_path.unlink(missing_ok=True)
        if temp_output_path is not None:
            temp_output_path.unlink(missing_ok=True)


def _build_export_zip(
    rows: list[dict[str, Any]],
    platform: str,
    apply_watermark: bool,
    include_originals: bool,
    watermark_settings: dict[str, Any] | None,
) -> bytes:
    spec = PLATFORM_SPECS[platform]
    zip_bytes = io.BytesIO()

    with zipfile.ZipFile(zip_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for row in rows:
            generation_id = row["id"]
            source_rel_path = row.get("upscaled_image_path") or row.get("image_path")
            source_path = _resolve_generation_source_path(source_rel_path)
            if source_path is None or not source_path.is_file():
                continue

            if include_originals:
                try:
                    archive.writestr(
                        f"original_{generation_id}.png",
                        source_path.read_bytes(),
                    )
                except OSError:
                    logger.warning(
                        "Failed to include original file for generation %s",
                        generation_id,
                    )

            try:
                processed: Image.Image | None = None
                with Image.open(source_path) as source_image:
                    processed = _resize_for_platform(
                        source_image, spec["max_long_edge"]
                    )

                if apply_watermark and watermark_settings is not None:
                    watermarked = _apply_watermark_with_service(
                        processed, watermark_settings
                    )
                    processed.close()
                    processed = watermarked

                image_buffer = io.BytesIO()
                processed.convert("RGB").save(
                    image_buffer,
                    format=spec["format"],
                    quality=spec["quality"],
                    optimize=True,
                )
                archive.writestr(
                    f"{platform}_{generation_id}.jpg",
                    image_buffer.getvalue(),
                )
            except Exception:
                logger.exception(
                    "Export processing failed for generation %s", generation_id
                )
                continue
            finally:
                if processed is not None:
                    processed.close()

    zip_bytes.seek(0)
    return zip_bytes.getvalue()


def _parse_metadata_ids(raw_ids: str | None) -> list[str]:
    if not raw_ids:
        return []

    ids: list[str] = []
    seen: set[str] = set()
    for raw in raw_ids.split(","):
        value = raw.strip()
        if not value or value in seen:
            continue
        ids.append(value)
        seen.add(value)
    return ids


def _normalize_metadata_item(row: dict[str, Any]) -> dict[str, Any]:
    item: dict[str, Any] = {}
    for field in METADATA_EXPORT_FIELDS:
        value = row.get(field)
        if field == "loras":
            if value is None:
                value = "[]"
            elif not isinstance(value, str):
                value = json.dumps(value, ensure_ascii=False)
        item[field] = value
    return item


async def _fetch_metadata_items(ids: list[str], limit: int) -> list[dict[str, Any]]:
    fields_sql = ", ".join(METADATA_EXPORT_FIELDS)

    async with get_db() as db:
        if ids:
            placeholders = ",".join("?" for _ in ids)
            cursor = await db.execute(
                f"""SELECT {fields_sql}
                    FROM generations
                    WHERE status = 'completed'
                      AND id IN ({placeholders})""",
                ids,
            )
            rows = await cursor.fetchall()
            row_by_id = {row["id"]: row for row in rows}
            ordered_rows = [row_by_id[generation_id] for generation_id in ids if generation_id in row_by_id]
            selected_rows = ordered_rows[:limit]
        else:
            cursor = await db.execute(
                f"""SELECT {fields_sql}
                    FROM generations
                    WHERE status = 'completed'
                    ORDER BY created_at DESC
                    LIMIT ?""",
                (limit,),
            )
            selected_rows = await cursor.fetchall()

    return [_normalize_metadata_item(row) for row in selected_rows]


def _build_metadata_csv(items: list[dict[str, Any]]) -> bytes:
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer)
    writer.writerow(METADATA_EXPORT_FIELDS)
    for item in items:
        writer.writerow(
            [item.get(field, "") if item.get(field) is not None else "" for field in METADATA_EXPORT_FIELDS]
        )
    return f"\ufeff{csv_buffer.getvalue()}".encode("utf-8")


async def _load_watermark_settings() -> dict[str, Any]:
    try:
        async with get_db() as db:
            await db.execute("INSERT OR IGNORE INTO watermark_settings (id) VALUES (1)")
            cursor = await db.execute(
                "SELECT * FROM watermark_settings WHERE id = 1"
            )
            row = await cursor.fetchone()
    except Exception:
        logger.exception("Failed to load watermark settings for export")
        return dict(_DEFAULT_WATERMARK_SETTINGS)

    if row is None:
        return dict(_DEFAULT_WATERMARK_SETTINGS)

    return {
        "enabled": bool(row.get("enabled", 0)),
        "text": row.get("text") or _DEFAULT_WATERMARK_SETTINGS["text"],
        "position": row.get("position")
        or _DEFAULT_WATERMARK_SETTINGS["position"],
        "opacity": row.get("opacity")
        if row.get("opacity") is not None
        else _DEFAULT_WATERMARK_SETTINGS["opacity"],
        "font_size": row.get("font_size")
        if row.get("font_size") is not None
        else _DEFAULT_WATERMARK_SETTINGS["font_size"],
        "padding": row.get("padding")
        if row.get("padding") is not None
        else _DEFAULT_WATERMARK_SETTINGS["padding"],
        "color": row.get("color") or _DEFAULT_WATERMARK_SETTINGS["color"],
    }


@router.get("/metadata", response_model=None)
async def export_metadata(
    export_format: Literal["csv", "json"] = Query(default="json", alias="format"),
    ids: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
) -> Response | dict[str, Any]:
    generation_ids = _parse_metadata_ids(ids)
    items = await _fetch_metadata_items(generation_ids, limit)

    if export_format == "csv":
        csv_payload = await asyncio.to_thread(_build_metadata_csv, items)
        filename = datetime.now(timezone.utc).strftime("hollowforge_metadata_%Y%m%d.csv")
        return Response(
            content=csv_payload,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return {
        "count": len(items),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }


@router.post("")
async def export_images(payload: ExportRequest) -> StreamingResponse:
    if not payload.generation_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="generation_ids must not be empty",
        )

    generation_ids = list(dict.fromkeys(payload.generation_ids))
    placeholders = ",".join("?" for _ in generation_ids)

    async with get_db() as db:
        cursor = await db.execute(
            f"""SELECT id, image_path, upscaled_image_path
                FROM generations
                WHERE status = 'completed'
                  AND image_path IS NOT NULL
                  AND id IN ({placeholders})""",
            generation_ids,
        )
        rows = await cursor.fetchall()

    row_by_id = {row["id"]: row for row in rows}
    ordered_rows = [row_by_id[generation_id] for generation_id in generation_ids if generation_id in row_by_id]

    watermark_settings: dict[str, Any] | None = None
    if payload.apply_watermark:
        watermark_settings = await _load_watermark_settings()

    zip_payload = await asyncio.to_thread(
        _build_export_zip,
        ordered_rows,
        payload.platform,
        payload.apply_watermark,
        payload.include_originals,
        watermark_settings,
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"export_{payload.platform}_{timestamp}.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(
        io.BytesIO(zip_payload),
        media_type="application/zip",
        headers=headers,
    )
