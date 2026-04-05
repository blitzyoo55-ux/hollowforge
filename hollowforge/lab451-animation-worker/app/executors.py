"""Execution adapters for the animation worker."""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx

from app.comfyui_client import ComfyUIClient
from app.config import settings
from app.workflows import (
    LTXV_REQUIRED_NODES,
    LTXVRequest,
    SDXL_STILL_REQUIRED_NODES,
    SDXLStillRequest,
    SDXL_IPADAPTER_REQUIRED_NODES,
    SDXLIPAdapterRequest,
    build_ltxv_2b_fast_workflow,
    build_sdxl_still_workflow,
    build_sdxl_ipadapter_frame_workflow,
)

_DUMMY_MP4_BYTES = b"DUMMY_MP4_CONTENT"
_DUMMY_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aE4kAAAAASUVORK5CYII="
)
_IMAGE_CONTENT_TYPE_TO_SUFFIX = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_SUPPORTED_LTXV_MODEL_PROFILES = {
    "ltxv_2b_fast",
    "ltx23_distilled_quality",
}
_SUPPORTED_EXECUTOR_BACKENDS = {
    "comfyui_pipeline",
    "comfyui_ltxv",
}
_SUPPORTED_BACKEND_FAMILIES = {
    "ltxv",
    "sdxl_ipadapter",
    "sdxl_still",
}


@dataclass
class SubmissionResult:
    external_job_id: str
    external_job_url: str | None


@dataclass
class CompletionResult:
    output_url: str | None
    error_message: str | None = None


class ExecutorAdapter(Protocol):
    async def submit(self, row: dict[str, Any]) -> SubmissionResult: ...

    async def wait_for_completion(self, worker_job_id: str) -> CompletionResult: ...


def _parse_json_object(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _pick_file_suffix(url: str, content_type: str | None) -> str:
    if content_type:
        clean_type = content_type.split(";", 1)[0].strip().lower()
        if clean_type in _IMAGE_CONTENT_TYPE_TO_SUFFIX:
            return _IMAGE_CONTENT_TYPE_TO_SUFFIX[clean_type]

    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".png"


def _pick_video_suffix(filename: str | None) -> str:
    if not filename:
        return ".mp4"
    suffix = Path(filename).suffix.lower()
    if suffix in {".mp4", ".mov", ".webm", ".mkv"}:
        return suffix
    return ".mp4"


def _default_prompt_from_row(row: dict[str, Any]) -> str:
    generation_metadata = _parse_json_object(row.get("generation_metadata")) or {}
    prompt = str(generation_metadata.get("prompt") or "").strip()
    if prompt:
        return prompt
    checkpoint = str(generation_metadata.get("checkpoint") or "").strip()
    if checkpoint:
        return f"Animate the source image using {checkpoint}"
    return "Animate the source image with subtle camera and body motion."


def _default_still_prompt_from_row(row: dict[str, Any]) -> str:
    generation_metadata = _parse_json_object(row.get("generation_metadata")) or {}
    prompt = str(generation_metadata.get("prompt") or "").strip()
    if prompt:
        return prompt
    return "Single-panel manga still, preserve character identity and panel composition."


def _cloudflare_access_headers() -> dict[str, str]:
    cf_access_client_id = settings.WORKER_CF_ACCESS_CLIENT_ID
    cf_access_client_secret = settings.WORKER_CF_ACCESS_CLIENT_SECRET
    if cf_access_client_id and cf_access_client_secret:
        return {
            "CF-Access-Client-Id": cf_access_client_id,
            "CF-Access-Client-Secret": cf_access_client_secret,
        }
    return {}


class StubExecutorAdapter:
    """Minimal backend used to verify orchestration and callback flow."""

    def __init__(self, outputs_dir: Path, public_base_url: str) -> None:
        self._outputs_dir = outputs_dir
        self._public_base_url = public_base_url.rstrip("/")
        self._target_tool: str | None = None

    async def submit(self, row: dict[str, Any]) -> SubmissionResult:
        worker_job_id = str(row["id"])
        self._target_tool = str(row.get("target_tool") or "").strip().lower()
        await asyncio.sleep(settings.WORKER_STUB_SUBMIT_DELAY_SEC)
        return SubmissionResult(
            external_job_id=f"stub-{worker_job_id}",
            external_job_url=f"{self._public_base_url}/api/v1/jobs/{worker_job_id}",
        )

    async def wait_for_completion(self, worker_job_id: str) -> CompletionResult:
        await asyncio.sleep(settings.WORKER_STUB_PROCESS_DELAY_SEC)
        is_comic_still = self._target_tool == "comic_panel_still"
        output_suffix = ".png" if is_comic_still else ".mp4"
        output_bytes = _DUMMY_PNG_BYTES if is_comic_still else _DUMMY_MP4_BYTES
        output_path = self._outputs_dir / f"{worker_job_id}{output_suffix}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(output_bytes)
        return CompletionResult(
            output_url=f"{self._public_base_url}/data/outputs/{worker_job_id}{output_suffix}",
        )


class ComfyUILTXVExecutorAdapter:
    """Submit local image-to-video jobs to a ComfyUI instance with native LTXV nodes."""

    def __init__(
        self,
        *,
        inputs_dir: Path,
        outputs_dir: Path,
        public_base_url: str,
        comfyui_url: str,
    ) -> None:
        self._inputs_dir = inputs_dir
        self._outputs_dir = outputs_dir
        self._public_base_url = public_base_url.rstrip("/")
        self._comfyui_url = comfyui_url.rstrip("/")
        self._client = ComfyUIClient(comfyui_url)
        self._job_mode: str | None = None
        self._prompt_id: str | None = None
        self._save_node_id: str | None = None
        self._sdxl_request: SDXLIPAdapterRequest | None = None
        self._sdxl_source_image_name: str | None = None

    def _history_url(self, prompt_id: str) -> str:
        return f"{self._comfyui_url}/history/{prompt_id}"

    async def _download_source_image(self, worker_job_id: str, source_image_url: str) -> Path:
        timeout = httpx.Timeout(60.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                source_image_url,
                headers=_cloudflare_access_headers(),
            )
            response.raise_for_status()
            suffix = _pick_file_suffix(source_image_url, response.headers.get("content-type"))
            local_path = self._inputs_dir / f"{worker_job_id}{suffix}"
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(response.content)
            return local_path

    async def _resolve_checkpoint_name(self) -> str:
        available = await self._client.get_models()
        preferred = settings.WORKER_COMFYUI_LTXV_CHECKPOINT
        fallback = settings.WORKER_COMFYUI_LTXV_CHECKPOINT_FALLBACK
        if available:
            if preferred in available:
                return preferred
            if fallback in available:
                return fallback
            raise RuntimeError(
                "No configured LTXV checkpoint found in ComfyUI models. "
                f"expected one of: {preferred}, {fallback}"
            )
        return preferred or fallback

    async def _resolve_text_encoder_name(self) -> str:
        available = await self._client.get_text_encoders()
        preferred = settings.WORKER_COMFYUI_LTXV_TEXT_ENCODER
        if available and preferred not in available:
            raise RuntimeError(
                "Configured LTXV text encoder is missing in ComfyUI. "
                f"expected: {preferred}"
            )
        return preferred

    async def _resolve_ipadapter_model_name(self) -> str:
        available = await self._client.get_ipadapter_models()
        preferred = settings.WORKER_COMFYUI_IPADAPTER_MODEL
        if available and preferred not in available:
            raise RuntimeError(
                "Configured IPAdapter model is missing in ComfyUI. "
                f"expected: {preferred}"
            )
        return preferred

    async def _resolve_clip_vision_name(self) -> str:
        available = await self._client.get_clip_vision_models()
        preferred = settings.WORKER_COMFYUI_CLIP_VISION_MODEL
        if available and preferred not in available:
            raise RuntimeError(
                "Configured CLIP vision model is missing in ComfyUI. "
                f"expected: {preferred}"
            )
        return preferred

    async def _resolve_still_checkpoint_name(self, preferred: str) -> str:
        checkpoint_name = preferred.strip()
        if not checkpoint_name:
            raise RuntimeError("Still generation job is missing a checkpoint name")
        available = await self._client.get_models()
        if available and checkpoint_name not in available:
            raise RuntimeError(
                "Configured still checkpoint is missing in ComfyUI. "
                f"expected: {checkpoint_name}"
            )
        return checkpoint_name

    def _build_microanim_schedule(
        self,
        request: SDXLIPAdapterRequest,
    ) -> list[tuple[str, float]]:
        if request.micro_motion_plan:
            return request.micro_motion_plan[: request.keyframes]
        base = max(0.02, min(0.3, request.denoise))
        return [
            ("eyes open, calm neutral expression, shoulders settled", base),
            ("tiny inhale, barely perceptible shoulder rise, eyes open", min(0.3, base + 0.01)),
            ("eyes softening, beginning a gentle blink", min(0.3, base + 0.02)),
            ("soft blink, calm expression, minimal movement", min(0.3, base + 0.03)),
            ("eyes reopening, same expression, same posture", min(0.3, base + 0.02)),
            ("tiny exhale, shoulders relaxing, eyes open", min(0.3, base + 0.01)),
            ("eyes open, calm neutral expression, shoulders settled", base),
        ][: request.keyframes]

    def _sequence_indices(self, frame_count: int) -> list[int]:
        if frame_count <= 1:
            return [0]
        forward = list(range(frame_count))
        backward = list(range(frame_count - 2, 0, -1))
        return forward + backward

    def _render_video_from_frames(
        self,
        *,
        frame_paths: list[Path],
        fps: float,
        output_path: Path,
    ) -> None:
        if not frame_paths:
            raise RuntimeError("No frames were generated for IPAdapter micro-animation")

        sequence_dir = output_path.parent / f"{output_path.stem}_frames"
        if sequence_dir.exists():
            shutil.rmtree(sequence_dir)
        sequence_dir.mkdir(parents=True, exist_ok=True)

        ordered_indices = self._sequence_indices(len(frame_paths))
        for sequence_index, frame_index in enumerate(ordered_indices, start=1):
            target = sequence_dir / f"frame_{sequence_index:03d}.png"
            shutil.copyfile(frame_paths[frame_index], target)

        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(max(1.0, fps)),
            "-i",
            str(sequence_dir / "frame_%03d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    async def submit(self, row: dict[str, Any]) -> SubmissionResult:
        worker_job_id = str(row["id"])
        request_json = _parse_json_object(row.get("request_json")) or {}
        target_tool = str(row.get("target_tool") or "").strip().lower()
        backend_family = str(request_json.get("backend_family") or "").strip().lower()
        model_profile = str(request_json.get("model_profile") or "").strip().lower()
        if backend_family and backend_family not in _SUPPORTED_BACKEND_FAMILIES:
            raise RuntimeError(
                "ComfyUI local executor only supports backend_family in "
                f"{', '.join(sorted(_SUPPORTED_BACKEND_FAMILIES))}, got {backend_family}"
            )
        if backend_family in {"", "ltxv"} and model_profile and model_profile not in _SUPPORTED_LTXV_MODEL_PROFILES:
            raise RuntimeError(
                "ComfyUI LTXV executor only supports model_profile in "
                f"{', '.join(sorted(_SUPPORTED_LTXV_MODEL_PROFILES))}"
            )

        if not await self._client.check_health():
            raise RuntimeError(
                f"ComfyUI is not reachable at {settings.WORKER_COMFYUI_URL}"
            )

        if target_tool == "comic_panel_still":
            generation_metadata = _parse_json_object(row.get("generation_metadata")) or {}
            default_checkpoint = str(generation_metadata.get("checkpoint") or "").strip()
            still_payload = request_json.get("still_generation")
            still_request = SDXLStillRequest.from_payload(
                still_payload if isinstance(still_payload, dict) else request_json,
                default_prompt=_default_still_prompt_from_row(row),
                default_checkpoint=default_checkpoint,
            )
            required_nodes = [
                node
                for node in SDXL_STILL_REQUIRED_NODES
                if node != "CLIPSetLastLayer" or still_request.clip_skip > 1
            ]
            if still_request.loras:
                required_nodes.append("LoraLoader")
            missing_nodes = await self._client.missing_nodes(required_nodes)
            if missing_nodes:
                raise RuntimeError(
                    "ComfyUI is missing required SDXL still nodes: "
                    f"{', '.join(missing_nodes)}"
                )
            still_request.checkpoint_name = await self._resolve_still_checkpoint_name(
                still_request.checkpoint_name
            )
            workflow, save_node_id = build_sdxl_still_workflow(
                request=still_request,
                filename_prefix=f"lab451_animation_worker/{worker_job_id}",
            )
            prompt_id = await self._client.submit_prompt(workflow)
            self._prompt_id = prompt_id
            self._save_node_id = save_node_id
            self._job_mode = "sdxl_still"
            return SubmissionResult(
                external_job_id=prompt_id,
                external_job_url=self._history_url(prompt_id),
            )

        source_image_url = str(row.get("source_image_url") or "").strip()
        if not source_image_url:
            raise RuntimeError("Worker job is missing source_image_url")
        local_source = await self._download_source_image(worker_job_id, source_image_url)
        uploaded_image_name = await self._client.upload_image(
            local_source,
            filename=local_source.name,
        )

        if backend_family == "sdxl_ipadapter":
            missing_nodes = await self._client.missing_nodes(SDXL_IPADAPTER_REQUIRED_NODES)
            if missing_nodes:
                raise RuntimeError(
                    f"ComfyUI is missing required SDXL IPAdapter nodes: {', '.join(missing_nodes)}"
                )
            generation_metadata = _parse_json_object(row.get("generation_metadata")) or {}
            default_checkpoint = str(generation_metadata.get("checkpoint") or "").strip()
            self._sdxl_request = SDXLIPAdapterRequest.from_payload(
                request_json,
                default_prompt=_default_prompt_from_row(row),
                default_checkpoint=default_checkpoint,
            )
            self._sdxl_request.ipadapter_file = await self._resolve_ipadapter_model_name()
            self._sdxl_request.clip_vision_name = await self._resolve_clip_vision_name()
            self._sdxl_source_image_name = uploaded_image_name
            self._job_mode = "sdxl_ipadapter"
            return SubmissionResult(
                external_job_id=f"microanim-{worker_job_id}",
                external_job_url=None,
            )

        missing_nodes = await self._client.missing_nodes(LTXV_REQUIRED_NODES)
        if missing_nodes:
            raise RuntimeError(
                f"ComfyUI is missing required LTXV nodes: {', '.join(missing_nodes)}"
            )

        prompt_request = LTXVRequest.from_payload(
            request_json,
            default_prompt=_default_prompt_from_row(row),
        )
        prompt_request.checkpoint_name = await self._resolve_checkpoint_name()
        prompt_request.text_encoder_name = await self._resolve_text_encoder_name()

        workflow, save_node_id = build_ltxv_2b_fast_workflow(
            uploaded_image_name=uploaded_image_name,
            request=prompt_request,
            filename_prefix=f"lab451_animation_worker/{worker_job_id}",
        )
        prompt_id = await self._client.submit_prompt(workflow)
        self._prompt_id = prompt_id
        self._save_node_id = save_node_id
        self._job_mode = "ltxv"
        return SubmissionResult(
            external_job_id=prompt_id,
            external_job_url=self._history_url(prompt_id),
        )

    async def wait_for_completion(self, worker_job_id: str) -> CompletionResult:
        if self._job_mode == "sdxl_ipadapter":
            if not self._sdxl_request or not self._sdxl_source_image_name:
                raise RuntimeError("SDXL IPAdapter job state was not initialized before completion wait")

            frame_paths: list[Path] = []
            try:
                schedule = self._build_microanim_schedule(self._sdxl_request)
                for frame_index, (frame_suffix, denoise) in enumerate(schedule):
                    frame_prompt = f"{self._sdxl_request.prompt}, {frame_suffix}"
                    frame_seed = self._sdxl_request.seed
                    workflow, save_node_id = build_sdxl_ipadapter_frame_workflow(
                        uploaded_image_name=self._sdxl_source_image_name,
                        request=self._sdxl_request,
                        filename_prefix=f"lab451_animation_worker/{worker_job_id}_frame_{frame_index:02d}",
                        frame_prompt=frame_prompt,
                        seed=frame_seed,
                        denoise=denoise,
                    )
                    prompt_id = await self._client.submit_prompt(workflow)
                    assets = await self._client.wait_for_completion(prompt_id, save_node_id)
                    if not assets:
                        raise RuntimeError(f"Frame {frame_index} completed without a saved image asset")
                    asset_bytes = await self._client.download_asset(assets[0])
                    frame_path = self._outputs_dir / f"{worker_job_id}_frame_{frame_index:02d}.png"
                    frame_path.write_bytes(asset_bytes)
                    frame_paths.append(frame_path)

                output_name = f"{worker_job_id}.mp4"
                output_path = self._outputs_dir / output_name
                self._render_video_from_frames(
                    frame_paths=frame_paths,
                    fps=self._sdxl_request.fps,
                    output_path=output_path,
                )
                return CompletionResult(
                    output_url=f"{self._public_base_url}/data/outputs/{output_name}",
                )
            finally:
                await self._client.close()

        if not self._prompt_id or not self._save_node_id:
            raise RuntimeError("ComfyUI prompt state was not initialized before completion wait")

        try:
            assets = await self._client.wait_for_completion(
                self._prompt_id,
                self._save_node_id,
            )
            if not assets:
                asset_kind = "image" if self._job_mode == "sdxl_still" else "video"
                raise RuntimeError(
                    f"ComfyUI finished without returning a saved {asset_kind} asset"
                )

            asset = assets[0]
            asset_bytes = await self._client.download_asset(asset)
            if self._job_mode == "sdxl_still":
                suffix = _pick_file_suffix(str(asset.get("filename") or ""), None)
                output_name = f"{worker_job_id}{suffix}"
                output_path = self._outputs_dir / output_name
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(asset_bytes)
                return CompletionResult(
                    output_url=f"{self._public_base_url}/data/outputs/{output_name}",
                )
            suffix = _pick_video_suffix(str(asset.get("filename") or ""))
            output_name = f"{worker_job_id}{suffix}"
            output_path = self._outputs_dir / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(asset_bytes)
            return CompletionResult(
                output_url=f"{self._public_base_url}/data/outputs/{output_name}",
            )
        finally:
            await self._client.close()


def build_executor(outputs_dir: Path, public_base_url: str) -> ExecutorAdapter:
    backend = settings.WORKER_EXECUTOR_BACKEND
    if backend == "stub":
        return StubExecutorAdapter(outputs_dir=outputs_dir, public_base_url=public_base_url)
    if backend in _SUPPORTED_EXECUTOR_BACKENDS:
        return ComfyUILTXVExecutorAdapter(
            inputs_dir=settings.INPUTS_DIR,
            outputs_dir=outputs_dir,
            public_base_url=public_base_url,
            comfyui_url=settings.WORKER_COMFYUI_URL,
        )
    raise ValueError(f"Unsupported WORKER_EXECUTOR_BACKEND: {backend}")
