"""Async ComfyUI API client using httpx."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from app.config import settings


class ComfyUIClient:
    """Thin async wrapper around the ComfyUI HTTP API."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.COMFYUI_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=60.0
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def submit_prompt(self, workflow: dict[str, Any]) -> str:
        """POST /prompt and return the prompt_id."""
        client = await self._get_client()
        payload = {
            "prompt": workflow,
            "client_id": f"hollowforge_{uuid.uuid4()}",
        }
        resp = await client.post("/prompt", json=payload)
        resp.raise_for_status()
        data = resp.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"Missing prompt_id in /prompt response: {data}")
        return prompt_id

    async def get_history(self, prompt_id: str) -> dict[str, Any] | None:
        """Fetch history entry for a specific prompt_id."""
        client = await self._get_client()
        resp = await client.get(f"/history/{prompt_id}")
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                if prompt_id in data:
                    return data[prompt_id]
                if data:
                    return next(iter(data.values()))

        # Fallback: query full history
        resp = await client.get("/history")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get(prompt_id)
        return None

    async def wait_for_completion(
        self,
        prompt_id: str,
        save_node_id: str,
        timeout: float | None = None,
        poll_interval: float | None = None,
    ) -> list[dict[str, Any]]:
        """Poll /history until the prompt finishes, then return image info list."""
        timeout = timeout or settings.GENERATION_TIMEOUT
        poll_interval = poll_interval or settings.POLL_INTERVAL
        elapsed = 0.0

        while True:
            if elapsed > timeout:
                raise TimeoutError(
                    f"Timeout waiting for completion. prompt_id={prompt_id}"
                )

            entry = await self.get_history(prompt_id)
            if entry:
                status = entry.get("status", {})
                if isinstance(status, dict):
                    for msg in status.get("messages", []):
                        if (
                            isinstance(msg, list)
                            and len(msg) >= 2
                            and msg[0] == "execution_error"
                        ):
                            raise RuntimeError(
                                f"ComfyUI execution_error: {msg[1]}"
                            )

                outputs = entry.get("outputs", {})
                node_output = (
                    outputs.get(save_node_id, {})
                    if isinstance(outputs, dict)
                    else {}
                )
                images = (
                    node_output.get("images", [])
                    if isinstance(node_output, dict)
                    else []
                )
                if images:
                    return images

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

    async def download_image(self, image_info: dict[str, Any]) -> bytes:
        """Download a generated image from ComfyUI /view endpoint."""
        client = await self._get_client()
        params = {
            "filename": image_info.get("filename", ""),
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "output"),
        }
        resp = await client.get("/view", params=params)
        resp.raise_for_status()
        return resp.content

    async def check_health(self) -> bool:
        """Return True if ComfyUI is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get("/system_stats", timeout=10.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def get_models(self) -> list[str]:
        """Return available checkpoint model names via /object_info."""
        try:
            client = await self._get_client()
            resp = await client.get("/object_info/CheckpointLoaderSimple")
            resp.raise_for_status()
            data = resp.json()
            node_info = data.get("CheckpointLoaderSimple", {})
            inputs = node_info.get("input", {}).get("required", {})
            ckpt_names = inputs.get("ckpt_name", [[]])[0]
            return list(ckpt_names) if isinstance(ckpt_names, list) else []
        except Exception:
            return []

    async def cancel_prompt(self, prompt_id: str) -> bool:
        """Attempt to cancel/interrupt a running prompt."""
        try:
            client = await self._get_client()
            resp = await client.post(
                "/interrupt", json={"prompt_id": prompt_id}
            )
            return resp.status_code == 200
        except Exception:
            return False
