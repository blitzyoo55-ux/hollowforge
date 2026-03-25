"""ComfyUI workflow builders for local animation backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings

LTXV_REQUIRED_NODES = (
    "LoadImage",
    "LTXVPreprocess",
    "CLIPLoader",
    "CLIPTextEncode",
    "CheckpointLoaderSimple",
    "LTXVImgToVideo",
    "LTXVConditioning",
    "LTXVScheduler",
    "RandomNoise",
    "ModelSamplingLTXV",
    "CFGGuider",
    "KSamplerSelect",
    "SamplerCustomAdvanced",
    "VAEDecode",
    "CreateVideo",
    "SaveVideo",
)
SDXL_IPADAPTER_REQUIRED_NODES = (
    "LoadImage",
    "ImageScale",
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "VAEEncode",
    "IPAdapterModelLoader",
    "CLIPVisionLoader",
    "IPAdapterAdvanced",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)


def _normalize_spatial(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(64, parsed)
    return ((parsed + 31) // 32) * 32


def _normalize_length(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(9, parsed)
    if (parsed - 1) % 8 == 0:
        return parsed
    return (((parsed - 1) // 8) + 1) * 8 + 1


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compose_prompt(
    default_prompt: str,
    prompt_suffix: str,
    inherit_generation_prompt: bool,
) -> str:
    base_prompt = str(default_prompt or "").strip()
    suffix = str(prompt_suffix or "").strip()
    if inherit_generation_prompt:
        if base_prompt and suffix:
            return f"{base_prompt}, {suffix}"
        return base_prompt or suffix
    return suffix or base_prompt


def _parse_micro_motion_plan(
    value: Any,
    *,
    base_denoise: float,
) -> list[tuple[str, float]]:
    if not isinstance(value, list):
        return []

    normalized: list[tuple[str, float]] = []
    for item in value:
        if isinstance(item, str):
            suffix = item.strip()
            if suffix:
                normalized.append((suffix, base_denoise))
            continue
        if not isinstance(item, dict):
            continue
        suffix = str(item.get("prompt") or item.get("suffix") or "").strip()
        if not suffix:
            continue
        denoise = min(
            1.0,
            max(
                0.0,
                _float_value(
                    item.get("denoise"),
                    _float_value(item.get("denoise_delta"), 0.0) + base_denoise,
                ),
            ),
        )
        normalized.append((suffix, denoise))
    return normalized


@dataclass
class LTXVRequest:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    frames: int
    fps: float
    steps: int
    cfg: float
    seed: int
    motion_strength: float
    sampler_name: str
    max_shift: float
    base_shift: float
    stretch: bool
    terminal: float
    checkpoint_name: str
    text_encoder_name: str
    image_compression: int

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any] | None,
        *,
        default_prompt: str,
    ) -> "LTXVRequest":
        payload = payload or {}
        prompt = _compose_prompt(
            default_prompt=default_prompt,
            prompt_suffix=str(payload.get("prompt") or ""),
            inherit_generation_prompt=bool(payload.get("inherit_generation_prompt")),
        )
        if not prompt:
            raise ValueError("Animation job requires a non-empty prompt")
        negative_prompt = str(
            payload.get("negative_prompt") or settings.WORKER_DEFAULT_NEGATIVE_PROMPT
        ).strip()
        return cls(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=_normalize_spatial(payload.get("width"), 768),
            height=_normalize_spatial(payload.get("height"), 512),
            frames=_normalize_length(payload.get("frames") or payload.get("length"), 49),
            fps=max(1.0, _float_value(payload.get("fps") or payload.get("frame_rate"), 12.0)),
            steps=max(1, int(payload.get("steps") or 24)),
            cfg=max(0.0, _float_value(payload.get("cfg"), 3.5)),
            seed=int(payload.get("seed") or 42),
            motion_strength=min(1.0, max(0.0, _float_value(payload.get("motion_strength"), 0.55))),
            sampler_name=str(payload.get("sampler_name") or "euler").strip() or "euler",
            max_shift=_float_value(payload.get("max_shift"), 2.05),
            base_shift=_float_value(payload.get("base_shift"), 0.95),
            stretch=bool(payload.get("stretch", True)),
            terminal=min(0.99, max(0.0, _float_value(payload.get("terminal"), 0.1))),
            checkpoint_name=str(
                payload.get("checkpoint_name") or settings.WORKER_COMFYUI_LTXV_CHECKPOINT
            ).strip(),
            text_encoder_name=str(
                payload.get("text_encoder_name") or settings.WORKER_COMFYUI_LTXV_TEXT_ENCODER
            ).strip(),
            image_compression=max(
                0,
                min(
                    100,
                    int(payload.get("image_compression") or settings.WORKER_COMFYUI_IMAGE_COMPRESSION),
                ),
            ),
        )


@dataclass
class SDXLIPAdapterRequest:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    cfg: float
    seed: int
    denoise: float
    sampler_name: str
    scheduler: str
    checkpoint_name: str
    ipadapter_file: str
    clip_vision_name: str
    ipadapter_weight: float
    ipadapter_weight_type: str
    ipadapter_start_at: float
    ipadapter_end_at: float
    embeds_scaling: str
    upscale_method: str
    crop: str
    keyframes: int
    fps: float
    micro_motion_plan: list[tuple[str, float]]

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any] | None,
        *,
        default_prompt: str,
        default_checkpoint: str,
    ) -> "SDXLIPAdapterRequest":
        payload = payload or {}
        prompt = _compose_prompt(
            default_prompt=default_prompt,
            prompt_suffix=str(payload.get("prompt") or ""),
            inherit_generation_prompt=bool(payload.get("inherit_generation_prompt")),
        )
        if not prompt:
            raise ValueError("Animation job requires a non-empty prompt")
        negative_prompt = str(
            payload.get("negative_prompt") or settings.WORKER_DEFAULT_NEGATIVE_PROMPT
        ).strip()
        checkpoint_name = str(payload.get("checkpoint_name") or default_checkpoint).strip()
        if not checkpoint_name:
            raise ValueError("Animation job requires a checkpoint_name or generation checkpoint")
        return cls(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=_normalize_spatial(payload.get("width"), 512),
            height=_normalize_spatial(payload.get("height"), 768),
            steps=max(1, int(payload.get("steps") or 28)),
            cfg=max(0.0, _float_value(payload.get("cfg"), 4.5)),
            seed=int(payload.get("seed") or 42),
            denoise=min(1.0, max(0.0, _float_value(payload.get("denoise"), 0.12))),
            sampler_name=str(payload.get("sampler_name") or "dpmpp_2m").strip() or "dpmpp_2m",
            scheduler=str(payload.get("scheduler") or "karras").strip() or "karras",
            checkpoint_name=checkpoint_name,
            ipadapter_file=str(
                payload.get("ipadapter_file") or settings.WORKER_COMFYUI_IPADAPTER_MODEL
            ).strip(),
            clip_vision_name=str(
                payload.get("clip_vision_name") or settings.WORKER_COMFYUI_CLIP_VISION_MODEL
            ).strip(),
            ipadapter_weight=_float_value(payload.get("ipadapter_weight"), 0.95),
            ipadapter_weight_type=str(payload.get("ipadapter_weight_type") or "linear").strip() or "linear",
            ipadapter_start_at=min(1.0, max(0.0, _float_value(payload.get("ipadapter_start_at"), 0.0))),
            ipadapter_end_at=min(1.0, max(0.0, _float_value(payload.get("ipadapter_end_at"), 1.0))),
            embeds_scaling=str(
                payload.get("embeds_scaling") or "K+mean(V) w/ C penalty"
            ).strip()
            or "K+mean(V) w/ C penalty",
            upscale_method=str(payload.get("upscale_method") or "lanczos").strip() or "lanczos",
            crop=str(payload.get("crop") or "center").strip() or "center",
            keyframes=max(3, int(payload.get("frames") or payload.get("keyframes") or 7)),
            fps=max(1.0, _float_value(payload.get("fps"), 6.0)),
            micro_motion_plan=_parse_micro_motion_plan(
                payload.get("micro_motion_plan"),
                base_denoise=min(1.0, max(0.0, _float_value(payload.get("denoise"), 0.12))),
            ),
        )


def build_ltxv_2b_fast_workflow(
    *,
    uploaded_image_name: str,
    request: LTXVRequest,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": uploaded_image_name,
            },
        },
        "2": {
            "class_type": "LTXVPreprocess",
            "inputs": {
                "image": ["1", 0],
                "img_compression": request.image_compression,
            },
        },
        "3": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": request.text_encoder_name,
                "type": "ltxv",
                "device": "default",
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": request.prompt,
                "clip": ["3", 0],
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": request.negative_prompt,
                "clip": ["3", 0],
            },
        },
        "6": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": request.checkpoint_name,
            },
        },
        "7": {
            "class_type": "LTXVImgToVideo",
            "inputs": {
                "positive": ["4", 0],
                "negative": ["5", 0],
                "vae": ["6", 2],
                "image": ["2", 0],
                "width": request.width,
                "height": request.height,
                "length": request.frames,
                "batch_size": 1,
                "strength": request.motion_strength,
            },
        },
        "8": {
            "class_type": "LTXVConditioning",
            "inputs": {
                "positive": ["7", 0],
                "negative": ["7", 1],
                "frame_rate": request.fps,
            },
        },
        "9": {
            "class_type": "LTXVScheduler",
            "inputs": {
                "steps": request.steps,
                "max_shift": request.max_shift,
                "base_shift": request.base_shift,
                "stretch": request.stretch,
                "terminal": request.terminal,
                "latent": ["7", 2],
            },
        },
        "10": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": request.seed,
            },
        },
        "11": {
            "class_type": "ModelSamplingLTXV",
            "inputs": {
                "model": ["6", 0],
                "max_shift": request.max_shift,
                "base_shift": request.base_shift,
                "latent": ["7", 2],
            },
        },
        "12": {
            "class_type": "CFGGuider",
            "inputs": {
                "model": ["11", 0],
                "positive": ["8", 0],
                "negative": ["8", 1],
                "cfg": request.cfg,
            },
        },
        "13": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": request.sampler_name,
            },
        },
        "14": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["10", 0],
                "guider": ["12", 0],
                "sampler": ["13", 0],
                "sigmas": ["9", 0],
                "latent_image": ["7", 2],
            },
        },
        "15": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["14", 0],
                "vae": ["6", 2],
            },
        },
        "16": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["15", 0],
                "fps": request.fps,
            },
        },
        "17": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["16", 0],
                "filename_prefix": filename_prefix,
                "format": "auto",
                "codec": "auto",
            },
        },
    }
    return workflow, "17"


def build_sdxl_ipadapter_frame_workflow(
    *,
    uploaded_image_name: str,
    request: SDXLIPAdapterRequest,
    filename_prefix: str,
    frame_prompt: str,
    seed: int,
    denoise: float,
) -> tuple[dict[str, Any], str]:
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": uploaded_image_name,
            },
        },
        "2": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["1", 0],
                "upscale_method": request.upscale_method,
                "width": request.width,
                "height": request.height,
                "crop": request.crop,
            },
        },
        "3": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": request.checkpoint_name,
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": frame_prompt,
                "clip": ["3", 1],
            },
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": request.negative_prompt,
                "clip": ["3", 1],
            },
        },
        "6": {
            "class_type": "VAEEncode",
            "inputs": {
                "pixels": ["2", 0],
                "vae": ["3", 2],
            },
        },
        "7": {
            "class_type": "IPAdapterModelLoader",
            "inputs": {
                "ipadapter_file": request.ipadapter_file,
            },
        },
        "8": {
            "class_type": "CLIPVisionLoader",
            "inputs": {
                "clip_name": request.clip_vision_name,
            },
        },
        "9": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": ["3", 0],
                "ipadapter": ["7", 0],
                "image": ["2", 0],
                "weight": request.ipadapter_weight,
                "weight_type": request.ipadapter_weight_type,
                "combine_embeds": "concat",
                "start_at": request.ipadapter_start_at,
                "end_at": request.ipadapter_end_at,
                "embeds_scaling": request.embeds_scaling,
                "clip_vision": ["8", 0],
            },
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["9", 0],
                "seed": seed,
                "steps": request.steps,
                "cfg": request.cfg,
                "sampler_name": request.sampler_name,
                "scheduler": request.scheduler,
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "denoise": denoise,
            },
        },
        "11": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["10", 0],
                "vae": ["3", 2],
            },
        },
        "12": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["11", 0],
                "filename_prefix": filename_prefix,
            },
        },
    }
    return workflow, "12"
