"""Async ComfyUI API client using httpx."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable

import httpx

from app.config import settings


class ComfyUIWaitCancelledError(RuntimeError):
    """Raised when a waiting prompt is cancelled by the caller."""


class ComfyUIClient:
    """Thin async wrapper around the ComfyUI HTTP API."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.COMFYUI_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._metadata_cache: dict[str, tuple[float, Any]] = {}
        self._metadata_cache_ttl_sec = max(0.0, settings.COMFYUI_METADATA_CACHE_TTL_SEC)
        self._metadata_lock = asyncio.Lock()

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

    def invalidate_metadata_cache(self) -> None:
        self._metadata_cache.clear()

    def _read_cached_metadata(self, cache_key: str) -> Any | None:
        if self._metadata_cache_ttl_sec <= 0:
            return None
        entry = self._metadata_cache.get(cache_key)
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= time.monotonic():
            self._metadata_cache.pop(cache_key, None)
            return None
        return value

    async def _get_cached_metadata(
        self,
        cache_key: str,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        cached = self._read_cached_metadata(cache_key)
        if cached is not None:
            return cached

        async with self._metadata_lock:
            cached = self._read_cached_metadata(cache_key)
            if cached is not None:
                return cached

            value = await loader()
            if self._metadata_cache_ttl_sec > 0:
                self._metadata_cache[cache_key] = (
                    time.monotonic() + self._metadata_cache_ttl_sec,
                    value,
                )
            return value

    async def _get_object_info(self, class_type: str) -> dict[str, Any]:
        async def load() -> dict[str, Any]:
            client = await self._get_client()
            resp = await client.get(f"/object_info/{class_type}")
            if resp.status_code != 200:
                return {}
            data = resp.json()
            return data if isinstance(data, dict) else {}

        payload = await self._get_cached_metadata(f"object-info:{class_type}", load)
        return payload if isinstance(payload, dict) else {}

    async def set_base_url(self, base_url: str) -> None:
        """Switch ComfyUI target URL at runtime."""
        normalized = base_url.strip().rstrip("/")
        if not normalized:
            raise ValueError("ComfyUI URL cannot be empty")
        if normalized == self.base_url:
            return
        await self.close()
        self.base_url = normalized
        self.invalidate_metadata_cache()

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
        cancel_check: Callable[[], bool | Awaitable[bool]] | None = None,
    ) -> list[dict[str, Any]]:
        """Poll /history until the prompt finishes, then return image info list."""
        timeout = timeout or settings.GENERATION_TIMEOUT
        poll_interval = poll_interval or settings.POLL_INTERVAL
        elapsed = 0.0

        while True:
            if cancel_check is not None:
                should_cancel = cancel_check()
                if asyncio.iscoroutine(should_cancel):
                    should_cancel = await should_cancel
                if should_cancel:
                    raise ComfyUIWaitCancelledError(
                        f"Cancelled while waiting for completion. prompt_id={prompt_id}"
                    )

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
            data = await self._get_object_info("CheckpointLoaderSimple")
            node_info = data.get("CheckpointLoaderSimple", {})
            inputs = node_info.get("input", {}).get("required", {})
            ckpt_names = inputs.get("ckpt_name", [[]])[0]
            return list(ckpt_names) if isinstance(ckpt_names, list) else []
        except Exception:
            return []

    async def get_lora_files(self) -> list[str]:
        """Return available LoRA filenames via /object_info."""
        try:
            data = await self._get_object_info("LoraLoader")
            node_info = data.get("LoraLoader", {})
            inputs = node_info.get("input", {}).get("required", {})
            lora_names = inputs.get("lora_name", [[]])[0]
            return list(lora_names) if isinstance(lora_names, list) else []
        except Exception:
            return []

    async def get_upscale_models(self) -> list[str]:
        """Return available upscale model filenames via /object_info."""
        try:
            data = await self._get_object_info("UpscaleModelLoader")
            node_info = data.get("UpscaleModelLoader", {})
            inputs = node_info.get("input", {}).get("required", {})
            names = inputs.get("model_name", [[]])[0]
            if not isinstance(names, list):
                names = inputs.get("upscale_model", [[]])[0]
            return list(names) if isinstance(names, list) else []
        except Exception:
            return []

    async def has_node(self, class_type: str) -> bool:
        """Return True if a ComfyUI node class is available in /object_info."""
        try:
            data = await self._get_object_info(class_type)
            return isinstance(data, dict) and class_type in data
        except Exception:
            return False

    async def missing_nodes(self, class_types: list[str] | tuple[str, ...]) -> list[str]:
        """Return the subset of requested node classes that are unavailable."""
        availability = await asyncio.gather(
            *(self.has_node(class_type) for class_type in class_types)
        )
        return [
            class_type
            for class_type, available in zip(class_types, availability)
            if not available
        ]

    async def get_samplers(self) -> list[str]:
        """Return available sampler names via /object_info."""
        try:
            data = await self._get_object_info("KSampler")
            node_info = data.get("KSampler", {})
            inputs = node_info.get("input", {}).get("required", {})
            names = inputs.get("sampler_name", [[]])[0]
            return list(names) if isinstance(names, list) else []
        except Exception:
            return ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "dpmpp_2m_sde"]

    async def get_schedulers(self) -> list[str]:
        """Return available scheduler names via /object_info."""
        try:
            data = await self._get_object_info("KSampler")
            node_info = data.get("KSampler", {})
            inputs = node_info.get("input", {}).get("required", {})
            names = inputs.get("scheduler", [[]])[0]
            return list(names) if isinstance(names, list) else []
        except Exception:
            return ["normal", "karras", "exponential", "sgm_uniform"]

    async def upload_image(self, file_path: str, filename: str) -> str:
        """Upload an image to ComfyUI input directory. Returns the filename used."""
        import pathlib
        client = await self._get_client()
        path = pathlib.Path(file_path)
        with open(path, "rb") as f:
            resp = await client.post(
                "/upload/image",
                files={"image": (filename, f, "image/png")},
                timeout=120.0,
            )
        resp.raise_for_status()
        data = resp.json()
        return data.get("name", filename)

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
