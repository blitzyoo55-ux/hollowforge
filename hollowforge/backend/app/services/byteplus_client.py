"""BytePlus API client (stub — replace with real credentials when ready).

Real BytePlus endpoints:
  DreamActor: POST https://visual.volcengineapi.com/?Action=SubmitDreamActorTask&Version=2022-08-31
  Seedance:   POST https://visual.volcengineapi.com/?Action=SubmitSeedanceTask&Version=2022-08-31
  Query:      POST https://visual.volcengineapi.com/?Action=QueryDreamActorTask (or QuerySeedanceTask)

Auth: HMAC-SHA256 (AK/SK). Set env vars BYTEPLUS_AK and BYTEPLUS_SK when ready.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

_BYTEPLUS_BASE_URL = "https://visual.volcengineapi.com/"
_DUMMY_QUERY_CALLS: dict[str, int] = {}


class BytePlusClient:
    """BytePlus Visual API client with dummy and real transport modes."""

    def __init__(self) -> None:
        self._ak = os.getenv("BYTEPLUS_AK", "").strip()
        self._sk = os.getenv("BYTEPLUS_SK", "").strip()
        self._is_dummy = not (self._ak and self._sk)
        self._timeout = httpx.Timeout(45.0)

        if self._is_dummy:
            logger.warning(
                "BytePlusClient running in DUMMY mode (BYTEPLUS_AK/BYTEPLUS_SK missing)."
            )
        else:
            logger.info("BytePlusClient running in REAL mode with AK/SK authentication.")

    @property
    def mode(self) -> str:
        return "dummy" if self._is_dummy else "real"

    async def submit_dreamactor_task(
        self,
        image_b64: str,
        template_video_b64: str,
    ) -> str:
        """Submit DreamActor motion-driving task and return a task_id."""
        if self._is_dummy:
            await asyncio.sleep(2)
            task_id = f"DUMMY_TASK_{uuid4().hex[:8]}"
            logger.info(
                "[BytePlus:DUMMY] submit_dreamactor_task accepted (image_b64=%d chars, video_b64=%d chars) -> %s",
                len(image_b64),
                len(template_video_b64),
                task_id,
            )
            return task_id

        payload = {
            "image": image_b64,
            "template_video": template_video_b64,
        }
        data = await self._signed_post("SubmitDreamActorTask", payload)
        task_id = (
            data.get("task_id")
            or data.get("TaskId")
            or data.get("data", {}).get("task_id")
            or data.get("data", {}).get("TaskId")
        )
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"BytePlus DreamActor submit missing task_id: {data}")
        return task_id

    async def submit_seedance_task(
        self,
        prompt: str,
        duration: int,
        files_meta: list[dict[str, Any]],
    ) -> str:
        """Submit Seedance task and return a task_id."""
        if self._is_dummy:
            await asyncio.sleep(2)
            task_id = f"DUMMY_TASK_{uuid4().hex[:8]}"
            logger.info(
                "[BytePlus:DUMMY] submit_seedance_task accepted (duration=%ss, files=%d) -> %s",
                duration,
                len(files_meta),
                task_id,
            )
            return task_id

        payload = {
            "prompt": prompt,
            "duration": duration,
            "files_meta": files_meta,
        }
        data = await self._signed_post("SubmitSeedanceTask", payload)
        task_id = (
            data.get("task_id")
            or data.get("TaskId")
            or data.get("data", {}).get("task_id")
            or data.get("data", {}).get("TaskId")
        )
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"BytePlus Seedance submit missing task_id: {data}")
        return task_id

    async def query_task(self, task_id: str, action: str) -> dict[str, Any]:
        """Query task status by BytePlus query action name."""
        if self._is_dummy:
            call_count = _DUMMY_QUERY_CALLS.get(task_id, 0) + 1
            _DUMMY_QUERY_CALLS[task_id] = call_count

            if call_count == 1:
                result = {"status": "processing", "video_url": None, "progress": 30}
            elif call_count == 2:
                result = {"status": "processing", "video_url": None, "progress": 70}
            else:
                result = {
                    "status": "succeeded",
                    "video_url": "https://example.com/dummy_video.mp4",
                    "progress": 100,
                }

            logger.info(
                "[BytePlus:DUMMY] query_task task=%s action=%s call=%d -> %s/%s%%",
                task_id,
                action,
                call_count,
                result["status"],
                result["progress"],
            )
            return result

        payload = {"task_id": task_id}
        data = await self._signed_post(action, payload)
        normalized = self._normalize_query_response(data)
        logger.info(
            "[BytePlus:REAL] query_task task=%s action=%s -> %s/%s%%",
            task_id,
            action,
            normalized["status"],
            normalized["progress"],
        )
        return normalized

    async def _signed_post(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Perform a signed POST request for BytePlus Visual APIs."""
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        payload_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        string_to_sign = f"{action}\n{timestamp}\n{payload_hash}"
        signature = hmac.new(
            self._sk.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-BytePlus-AK": self._ak,
            "X-BytePlus-Timestamp": timestamp,
            "X-BytePlus-Signature": signature,
        }
        params = {
            "Action": action,
            "Version": "2022-08-31",
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                _BYTEPLUS_BASE_URL,
                params=params,
                content=payload_json.encode("utf-8"),
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError(f"Unexpected BytePlus response type for {action}: {type(data)}")
        return data

    @staticmethod
    def _normalize_query_response(data: dict[str, Any]) -> dict[str, Any]:
        status_raw = (
            data.get("status")
            or data.get("Status")
            or data.get("data", {}).get("status")
            or data.get("data", {}).get("Status")
            or "processing"
        )
        status_map = {
            "success": "succeeded",
            "succeeded": "succeeded",
            "done": "succeeded",
            "running": "processing",
            "processing": "processing",
            "pending": "processing",
            "queued": "processing",
            "failed": "failed",
            "error": "failed",
        }
        status = status_map.get(str(status_raw).strip().lower(), "processing")

        progress_raw = (
            data.get("progress")
            or data.get("Progress")
            or data.get("data", {}).get("progress")
            or data.get("data", {}).get("Progress")
            or 0
        )
        try:
            progress = max(0, min(100, int(progress_raw)))
        except (TypeError, ValueError):
            progress = 0

        video_url = (
            data.get("video_url")
            or data.get("VideoUrl")
            or data.get("data", {}).get("video_url")
            or data.get("data", {}).get("VideoUrl")
        )
        if video_url is not None:
            video_url = str(video_url)

        return {
            "status": status,
            "video_url": video_url,
            "progress": progress,
        }
