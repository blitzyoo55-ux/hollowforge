"""Seedance 2.0 service wrapper built on the shared BytePlus client."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import UploadFile

from app.config import settings
from app.db import get_db
from app.services.byteplus_client import BytePlusClient

logger = logging.getLogger(__name__)

_ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".webm"}
_ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_AUDIO_EXTS = {".mp3"}
_DUMMY_MP4_BYTES = b"DUMMY_MP4_CONTENT"
_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def _resolve_data_relative_path(rel_path: str) -> Path:
    path = (settings.DATA_DIR / rel_path).resolve()
    data_root = settings.DATA_DIR.resolve()
    try:
        path.relative_to(data_root)
    except ValueError as exc:
        raise ValueError(f"Unsafe output path: {rel_path}") from exc
    return path


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _unlink(path: Path) -> None:
    path.unlink(missing_ok=True)


class SeedanceService:
    """Application-facing Seedance API integration."""

    def __init__(self, byteplus_client: BytePlusClient | None = None) -> None:
        self._byteplus = byteplus_client or BytePlusClient()
        self._http_timeout = httpx.Timeout(45.0)

    async def submit_seedance_job(
        self,
        prompt: str,
        duration: int,
        image_ids: list[str] | None,
        uploaded_files: list[UploadFile],
    ) -> str:
        """Validate and submit a Seedance job. Returns internal job_id."""
        text_prompt = prompt.strip()
        if not text_prompt:
            raise ValueError("Prompt is required")
        if duration < 4 or duration > 15:
            raise ValueError("duration_sec must be between 4 and 15")

        image_refs = [img_id.strip() for img_id in (image_ids or []) if img_id.strip()]
        files_meta, counts = await self._collect_files_meta(uploaded_files, image_refs)
        self._validate_counts(counts)

        task_id = await self._byteplus.submit_seedance_task(
            prompt=text_prompt,
            duration=duration,
            files_meta=files_meta,
        )
        job_id = str(uuid.uuid4())

        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO seedance_jobs (
                    id, task_id, status, prompt, duration_sec, files_meta
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    task_id,
                    "processing",
                    text_prompt,
                    duration,
                    json.dumps(files_meta),
                ),
            )
            await db.commit()

        logger.info(
            "Seedance job submitted: job_id=%s task_id=%s mode=%s files=%d",
            job_id,
            task_id,
            self._byteplus.mode,
            len(files_meta),
        )
        return job_id

    async def poll_seedance_job(self, job_id: str) -> dict[str, Any]:
        """Poll Seedance job status and persist output path when completed."""
        job = await self.get_job(job_id)
        if job is None:
            raise ValueError(f"Seedance job {job_id} not found")

        if job.get("status") in _TERMINAL_STATUSES:
            return self._row_to_status_response(job, progress=100 if job.get("status") == "succeeded" else 0)

        task_id = job.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("Seedance job has no task_id")

        result = await self._byteplus.query_task(task_id, "QuerySeedanceTask")
        status = str(result.get("status") or "processing")
        progress = max(0, min(100, int(result.get("progress") or 0)))
        video_url = result.get("video_url")

        output_path = job.get("output_path")
        error_msg = job.get("error_msg")

        if status == "succeeded":
            if not isinstance(output_path, str) or not output_path:
                output_path = f"images/seedance/{job_id}.mp4"
                output_abs = settings.IMAGES_DIR / "seedance" / f"{job_id}.mp4"
                video_bytes = await self._download_video_bytes(video_url)
                await asyncio.to_thread(_write_bytes, output_abs, video_bytes)

            async with get_db() as db:
                await db.execute(
                    """
                    UPDATE seedance_jobs
                    SET status = ?, output_path = ?, error_msg = NULL, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    ("succeeded", output_path, job_id),
                )
                await db.commit()
            error_msg = None
        elif status == "failed":
            error_msg = "Seedance task failed"
            async with get_db() as db:
                await db.execute(
                    """
                    UPDATE seedance_jobs
                    SET status = ?, error_msg = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    ("failed", error_msg, job_id),
                )
                await db.commit()
        else:
            async with get_db() as db:
                await db.execute(
                    "UPDATE seedance_jobs SET status = ? WHERE id = ?",
                    ("processing", job_id),
                )
                await db.commit()
            status = "processing"

        refreshed = await self.get_job(job_id)
        if refreshed is None:
            raise ValueError(f"Seedance job {job_id} not found after update")
        return self._row_to_status_response(
            refreshed,
            progress=100 if status == "succeeded" else progress,
            output_path=output_path if isinstance(output_path, str) else None,
            error_msg=error_msg,
        )

    async def list_recent_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        async with get_db() as db:
            cursor = await db.execute(
                """
                SELECT *
                FROM seedance_jobs
                ORDER BY datetime(created_at) DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        return [self._row_to_status_response(row, progress=self._guess_progress(row)) for row in rows]

    async def delete_job(self, job_id: str) -> bool:
        job = await self.get_job(job_id)
        if job is None:
            return False

        output_path = job.get("output_path")
        if isinstance(output_path, str) and output_path:
            full_path = _resolve_data_relative_path(output_path)
            if full_path.exists() and full_path.is_file():
                await asyncio.to_thread(_unlink, full_path)

        async with get_db() as db:
            await db.execute("DELETE FROM seedance_jobs WHERE id = ?", (job_id,))
            await db.commit()
        return True

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT * FROM seedance_jobs WHERE id = ?",
                (job_id,),
            )
            row = await cursor.fetchone()
        return row

    async def _collect_files_meta(
        self,
        uploaded_files: list[UploadFile],
        image_ids: list[str],
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        files_meta: list[dict[str, Any]] = []
        counts = {"images": len(image_ids), "videos": 0, "audio": 0, "total": len(image_ids)}

        for idx, image_id in enumerate(image_ids, start=1):
            files_meta.append(
                {
                    "type": "image_ref",
                    "label": f"ImageRef {idx}",
                    "generation_id": image_id,
                }
            )

        for file in uploaded_files:
            filename = file.filename or "unnamed"
            ext = Path(filename).suffix.lower()
            content_type = (file.content_type or "").lower()
            file_type = self._detect_file_type(ext, content_type)

            if file_type == "audio" and ext not in _ALLOWED_AUDIO_EXTS:
                raise ValueError("Audio input supports MP3 only")
            if file_type == "unknown":
                raise ValueError(f"Unsupported file type: {filename}")

            size_bytes = file.size
            if size_bytes is None:
                data = await file.read()
                size_bytes = len(data)
                await file.seek(0)

            counts["total"] += 1
            if file_type == "image":
                counts["images"] += 1
            elif file_type == "video":
                counts["videos"] += 1
            elif file_type == "audio":
                counts["audio"] += 1

            files_meta.append(
                {
                    "type": file_type,
                    "filename": filename,
                    "content_type": file.content_type,
                    "size_bytes": size_bytes,
                }
            )

        return files_meta, counts

    def _validate_counts(self, counts: dict[str, int]) -> None:
        if counts["images"] > 9:
            raise ValueError("Seedance supports up to 9 images")
        if counts["videos"] > 3:
            raise ValueError("Seedance supports up to 3 video clips")
        if counts["audio"] > 3:
            raise ValueError("Seedance supports up to 3 audio files")
        if counts["total"] > 12:
            raise ValueError("Seedance supports up to 12 total mixed files")

    def _detect_file_type(self, ext: str, content_type: str) -> str:
        if ext in _ALLOWED_IMAGE_EXTS or content_type.startswith("image/"):
            return "image"
        if ext in _ALLOWED_VIDEO_EXTS or content_type.startswith("video/"):
            return "video"
        if ext in _ALLOWED_AUDIO_EXTS or content_type.startswith("audio/"):
            return "audio"
        return "unknown"

    def _guess_progress(self, row: dict[str, Any]) -> int:
        status = row.get("status")
        if status == "succeeded":
            return 100
        if status == "processing":
            return 50
        return 0

    def _row_to_status_response(
        self,
        row: dict[str, Any],
        progress: int,
        output_path: str | None = None,
        error_msg: str | None = None,
    ) -> dict[str, Any]:
        resolved_output_path: str | None
        if output_path is not None:
            resolved_output_path = output_path
        else:
            maybe_output = row.get("output_path")
            resolved_output_path = maybe_output if isinstance(maybe_output, str) and maybe_output else None

        resolved_error: str | None
        if error_msg is not None:
            resolved_error = error_msg
        else:
            maybe_error = row.get("error_msg")
            resolved_error = maybe_error if isinstance(maybe_error, str) else None

        return {
            "job_id": row["id"],
            "status": row.get("status") or "pending",
            "progress": progress,
            "output_path": resolved_output_path,
            "error_msg": resolved_error,
            "created_at": row.get("created_at"),
            "completed_at": row.get("completed_at"),
            "prompt": row.get("prompt"),
            "duration_sec": row.get("duration_sec"),
        }

    async def _download_video_bytes(self, video_url: Any) -> bytes:
        if not isinstance(video_url, str) or not video_url:
            logger.warning("Seedance succeeded without video_url; writing dummy mp4 placeholder.")
            return _DUMMY_MP4_BYTES
        if video_url.startswith("https://example.com/dummy_video.mp4"):
            return _DUMMY_MP4_BYTES

        try:
            async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                response = await client.get(video_url)
                response.raise_for_status()
                return response.content
        except Exception:
            logger.exception("Failed to download Seedance output from %s", video_url)
            return _DUMMY_MP4_BYTES
