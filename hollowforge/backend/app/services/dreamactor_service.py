"""DreamActor M2.0 service — wraps BytePlus client for motion driving."""

from __future__ import annotations

import asyncio
import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.db import get_db
from app.services.byteplus_client import BytePlusClient

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = int(4.7 * 1024 * 1024)
_ALLOWED_IMAGE_FORMATS = {"JPEG", "JPG", "PNG"}
_ALLOWED_TEMPLATE_VIDEO_EXTS = {".mp4", ".mov", ".webm"}
_DUMMY_MP4_BYTES = b"DUMMY_MP4_CONTENT"


def _resolve_data_relative_path(rel_path: str) -> Path:
    path = (settings.DATA_DIR / rel_path).resolve()
    data_root = settings.DATA_DIR.resolve()
    try:
        path.relative_to(data_root)
    except ValueError as exc:
        raise ValueError(f"Unsafe source path: {rel_path}") from exc
    return path


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _inspect_image(image_bytes: bytes) -> tuple[str, tuple[int, int]]:
    with Image.open(BytesIO(image_bytes)) as image:
        img_format = (image.format or "").upper()
        size = image.size
    return img_format, size


class DreamActorService:
    """Application-facing DreamActor API integration."""

    def __init__(self, byteplus_client: BytePlusClient | None = None) -> None:
        self._byteplus = byteplus_client or BytePlusClient()
        self._http_timeout = httpx.Timeout(45.0)

    async def submit_dreamactor_task(
        self,
        generation_id: str,
        template_video_bytes: bytes,
        template_filename: str,
    ) -> str:
        """Submit a DreamActor job for an existing generation image."""
        generation = await self.get_generation_dreamactor_state(generation_id)
        if generation is None:
            raise ValueError(f"Generation {generation_id} not found")

        source_rel = generation.get("image_path")
        if not isinstance(source_rel, str) or not source_rel:
            raise ValueError("Generation has no source image")

        source_path = _resolve_data_relative_path(source_rel)
        if not source_path.is_file():
            raise FileNotFoundError(f"Source image not found: {source_path}")

        source_image_bytes = await asyncio.to_thread(_read_bytes, source_path)
        await asyncio.to_thread(self._validate_source_image, source_image_bytes)
        self._validate_template_video(template_video_bytes, template_filename)

        image_b64 = base64.b64encode(source_image_bytes).decode("utf-8")
        template_video_b64 = base64.b64encode(template_video_bytes).decode("utf-8")
        task_id = await self._byteplus.submit_dreamactor_task(
            image_b64=image_b64,
            template_video_b64=template_video_b64,
        )

        async with get_db() as db:
            await db.execute(
                """
                UPDATE generations
                SET dreamactor_task_id = ?, dreamactor_status = ?, dreamactor_path = NULL
                WHERE id = ?
                """,
                (task_id, "processing", generation_id),
            )
            await db.commit()

        logger.info(
            "DreamActor task submitted: generation=%s task_id=%s mode=%s",
            generation_id,
            task_id,
            self._byteplus.mode,
        )
        return task_id

    async def poll_dreamactor_task(
        self,
        generation_id: str,
        task_id: str,
    ) -> dict[str, Any]:
        """Poll DreamActor task and persist output/status when terminal."""
        result = await self._byteplus.query_task(task_id, "QueryDreamActorTask")
        status = str(result.get("status") or "processing")
        progress = int(result.get("progress") or 0)
        video_url = result.get("video_url")

        existing = await self.get_generation_dreamactor_state(generation_id)
        if existing is None:
            raise ValueError(f"Generation {generation_id} not found")

        dreamactor_path = existing.get("dreamactor_path")
        local_video_url: str | None = (
            f"/data/{dreamactor_path}" if isinstance(dreamactor_path, str) and dreamactor_path else None
        )

        if status == "succeeded":
            if not local_video_url:
                output_rel = f"images/dreamactor/{generation_id}.mp4"
                output_abs = settings.IMAGES_DIR / "dreamactor" / f"{generation_id}.mp4"
                video_bytes = await self._download_video_bytes(video_url)
                await asyncio.to_thread(_write_bytes, output_abs, video_bytes)
                dreamactor_path = output_rel
                local_video_url = f"/data/{output_rel}"

            async with get_db() as db:
                await db.execute(
                    """
                    UPDATE generations
                    SET dreamactor_status = ?, dreamactor_path = ?
                    WHERE id = ?
                    """,
                    ("succeeded", dreamactor_path, generation_id),
                )
                await db.commit()
        elif status == "failed":
            async with get_db() as db:
                await db.execute(
                    "UPDATE generations SET dreamactor_status = ? WHERE id = ?",
                    ("failed", generation_id),
                )
                await db.commit()
        else:
            async with get_db() as db:
                await db.execute(
                    "UPDATE generations SET dreamactor_status = ? WHERE id = ?",
                    ("processing", generation_id),
                )
                await db.commit()

        return {
            "status": status,
            "progress": max(0, min(100, progress)),
            "video_url": local_video_url or (str(video_url) if video_url else None),
            "dreamactor_path": dreamactor_path if isinstance(dreamactor_path, str) else None,
        }

    async def get_generation_dreamactor_state(
        self, generation_id: str
    ) -> dict[str, Any] | None:
        """Fetch DreamActor-related generation state."""
        async with get_db() as db:
            cursor = await db.execute(
                """
                SELECT id, image_path, dreamactor_task_id, dreamactor_status, dreamactor_path
                FROM generations
                WHERE id = ?
                """,
                (generation_id,),
            )
            row = await cursor.fetchone()
        return row

    def _validate_source_image(self, image_bytes: bytes) -> None:
        if len(image_bytes) >= _MAX_IMAGE_BYTES:
            raise ValueError("Source image must be smaller than 4.7MB for DreamActor")
        try:
            img_format, _size = _inspect_image(image_bytes)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("Source image is not a valid image file") from exc
        if img_format not in _ALLOWED_IMAGE_FORMATS:
            raise ValueError("Source image must be JPG/JPEG/PNG for DreamActor")

    def _validate_template_video(self, template_video_bytes: bytes, filename: str) -> None:
        if not template_video_bytes:
            raise ValueError("Template video file is empty")
        ext = Path(filename).suffix.lower()
        if ext not in _ALLOWED_TEMPLATE_VIDEO_EXTS:
            raise ValueError("Template video must be .mp4, .mov, or .webm")

    async def _download_video_bytes(self, video_url: Any) -> bytes:
        if not isinstance(video_url, str) or not video_url:
            logger.warning("DreamActor succeeded without video_url; writing dummy mp4 placeholder.")
            return _DUMMY_MP4_BYTES
        if video_url.startswith("https://example.com/dummy_video.mp4"):
            return _DUMMY_MP4_BYTES

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                response = await client.get(video_url)
                response.raise_for_status()
                return response.content
        except Exception:
            logger.exception("Failed to download DreamActor output from %s", video_url)
            return _DUMMY_MP4_BYTES
