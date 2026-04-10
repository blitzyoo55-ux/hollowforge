"""Minimal async ComfyUI client for the animation worker."""

from __future__ import annotations

import asyncio
import pathlib
import uuid
from typing import Any

import httpx

from app.config import settings


class ComfyUIClient:
    """Small wrapper around the ComfyUI HTTP API."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.WORKER_COMFYUI_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=120.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def submit_prompt(self, workflow: dict[str, Any]) -> str:
        client = await self._get_client()
        response = await client.post(
            "/prompt",
            json={
                "prompt": workflow,
                "client_id": f"lab451_animation_worker_{uuid.uuid4()}",
            },
        )
        response.raise_for_status()
        data = response.json()
        prompt_id = data.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise RuntimeError(f"Missing prompt_id in ComfyUI response: {data}")
        return prompt_id

    async def get_history(self, prompt_id: str) -> dict[str, Any] | None:
        client = await self._get_client()
        response = await client.get(f"/history/{prompt_id}")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                if prompt_id in data:
                    return data[prompt_id]
                if data:
                    return next(iter(data.values()))
        response = await client.get("/history")
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data.get(prompt_id)
        return None

    async def wait_for_completion(
        self,
        prompt_id: str,
        save_node_id: str,
        timeout_sec: float | None = None,
        poll_interval_sec: float | None = None,
    ) -> list[dict[str, Any]]:
        timeout_sec = timeout_sec or settings.WORKER_COMFYUI_TIMEOUT_SEC
        poll_interval_sec = poll_interval_sec or settings.WORKER_COMFYUI_POLL_INTERVAL_SEC
        elapsed = 0.0
        while True:
            if elapsed > timeout_sec:
                raise TimeoutError(f"Timeout waiting for ComfyUI prompt {prompt_id}")

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
                            raise RuntimeError(f"ComfyUI execution_error: {msg[1]}")

                outputs = entry.get("outputs", {})
                node_output = outputs.get(save_node_id, {}) if isinstance(outputs, dict) else {}
                assets = node_output.get("images", []) if isinstance(node_output, dict) else []
                if assets:
                    return assets

            await asyncio.sleep(poll_interval_sec)
            elapsed += poll_interval_sec

    async def download_asset(self, asset: dict[str, Any]) -> bytes:
        client = await self._get_client()
        response = await client.get(
            "/view",
            params={
                "filename": asset.get("filename", ""),
                "subfolder": asset.get("subfolder", ""),
                "type": asset.get("type", "output"),
            },
        )
        response.raise_for_status()
        return response.content

    async def upload_image(self, file_path: pathlib.Path, filename: str) -> str:
        client = await self._get_client()
        with file_path.open("rb") as handle:
            response = await client.post(
                "/upload/image",
                files={"image": (filename, handle, "image/png")},
            )
        response.raise_for_status()
        data = response.json()
        uploaded_name = data.get("name", filename)
        if not isinstance(uploaded_name, str) or not uploaded_name:
            raise RuntimeError(f"Unexpected upload response from ComfyUI: {data}")
        return uploaded_name

    async def check_health(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/system_stats", timeout=10.0)
            return response.status_code == 200
        except Exception:
            return False

    async def _get_object_info(self, class_type: str) -> dict[str, Any]:
        client = await self._get_client()
        response = await client.get(f"/object_info/{class_type}")
        if response.status_code != 200:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def has_node(self, class_type: str) -> bool:
        data = await self._get_object_info(class_type)
        return class_type in data

    async def missing_nodes(self, class_types: list[str] | tuple[str, ...]) -> list[str]:
        availability = await asyncio.gather(*(self.has_node(class_type) for class_type in class_types))
        return [
            class_type
            for class_type, available in zip(class_types, availability)
            if not available
        ]

    async def get_models(self) -> list[str]:
        data = await self._get_object_info("CheckpointLoaderSimple")
        node_info = data.get("CheckpointLoaderSimple", {})
        inputs = node_info.get("input", {}).get("required", {})
        models = inputs.get("ckpt_name", [[]])[0]
        return list(models) if isinstance(models, list) else []

    async def get_lora_files(self) -> list[str]:
        data = await self._get_object_info("LoraLoader")
        node_info = data.get("LoraLoader", {})
        inputs = node_info.get("input", {}).get("required", {})
        loras = inputs.get("lora_name", [[]])[0]
        return list(loras) if isinstance(loras, list) else []

    async def get_text_encoders(self) -> list[str]:
        data = await self._get_object_info("CLIPLoader")
        node_info = data.get("CLIPLoader", {})
        inputs = node_info.get("input", {}).get("required", {})
        encoders = inputs.get("clip_name", [[]])[0]
        return list(encoders) if isinstance(encoders, list) else []

    async def get_clip_vision_models(self) -> list[str]:
        data = await self._get_object_info("CLIPVisionLoader")
        node_info = data.get("CLIPVisionLoader", {})
        inputs = node_info.get("input", {}).get("required", {})
        models = inputs.get("clip_name", [[]])[0]
        return list(models) if isinstance(models, list) else []

    async def get_ipadapter_models(self) -> list[str]:
        data = await self._get_object_info("IPAdapterModelLoader")
        node_info = data.get("IPAdapterModelLoader", {})
        inputs = node_info.get("input", {}).get("required", {})
        models = inputs.get("ipadapter_file", [[]])[0]
        return list(models) if isinstance(models, list) else []
