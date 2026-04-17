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
    "CheckpointLoaderSimple",
    "CLIPTextEncodeSDXL",
    "EmptyLatentImage",
    "IPAdapterModelLoader",
    "CLIPVisionLoader",
    "IPAdapterAdvanced",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)
SDXL_STILL_REQUIRED_NODES = (
    "CheckpointLoaderSimple",
    "CLIPSetLastLayer",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)
_SUPPORTED_STILL_ADAPTER_PROFILES = {
    "general",
    "plus_face",
    "faceid_plus_v2",
}


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


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
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


def _parse_loras(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or item.get("name") or "").strip()
        if not filename:
            continue
        normalized.append(
            {
                "filename": filename,
                "strength": _float_value(item.get("strength"), 1.0),
            }
        )
    return normalized


def _parse_reference_images(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError("Reference-guided still job requires a reference_images list")

    normalized = tuple(str(item).strip() for item in value if str(item).strip())
    if not normalized:
        raise ValueError("Reference-guided still job requires at least one reference image")
    return normalized


def _resolve_still_adapter_profile(payload: dict[str, Any]) -> str:
    adapter_profile = str(payload.get("adapter_profile") or "general").strip().lower()
    if adapter_profile not in _SUPPORTED_STILL_ADAPTER_PROFILES:
        raise ValueError(
            "Unsupported adapter profile for reference-guided still job: "
            f"{adapter_profile}"
        )
    return adapter_profile


def _resolve_ipadapter_file_for_profile(payload: dict[str, Any], adapter_profile: str) -> str:
    explicit = str(payload.get("ipadapter_file") or "").strip()
    if explicit:
        return explicit
    if adapter_profile == "plus_face":
        return settings.WORKER_COMFYUI_IPADAPTER_PLUS_FACE_MODEL
    if adapter_profile == "faceid_plus_v2":
        return settings.WORKER_COMFYUI_IPADAPTER_FACEID_MODEL
    return settings.WORKER_COMFYUI_IPADAPTER_MODEL


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
    clip_skip: int
    loras: list[dict[str, Any]]
    adapter_profile: str
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
    repair_enabled: bool
    repair_denoise: float
    repair_strength: float

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
        adapter_profile = _resolve_still_adapter_profile(payload)
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
            clip_skip=max(1, _int_value(payload.get("clip_skip"), 1)),
            loras=_parse_loras(payload.get("loras")),
            adapter_profile=adapter_profile,
            ipadapter_file=_resolve_ipadapter_file_for_profile(payload, adapter_profile),
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
            repair_enabled=bool(payload.get("repair_enabled")),
            repair_denoise=min(1.0, max(0.0, _float_value(payload.get("repair_denoise"), 0.28))),
            repair_strength=min(1.0, max(0.0, _float_value(payload.get("repair_strength"), 0.82))),
        )


@dataclass
class SDXLStillRequest:
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    cfg: float
    seed: int
    sampler_name: str
    scheduler: str
    checkpoint_name: str
    clip_skip: int
    loras: list[dict[str, Any]]

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any] | None,
        *,
        default_prompt: str,
        default_checkpoint: str,
    ) -> "SDXLStillRequest":
        payload = payload or {}
        prompt = _compose_prompt(
            default_prompt=default_prompt,
            prompt_suffix=str(payload.get("prompt") or ""),
            inherit_generation_prompt=bool(payload.get("inherit_generation_prompt")),
        )
        if not prompt:
            raise ValueError("Still generation job requires a non-empty prompt")
        negative_prompt = str(
            payload.get("negative_prompt") or settings.WORKER_DEFAULT_NEGATIVE_PROMPT
        ).strip()
        checkpoint_name = str(
            payload.get("checkpoint_name") or payload.get("checkpoint") or default_checkpoint
        ).strip()
        if not checkpoint_name:
            raise ValueError("Still generation job requires a checkpoint")
        return cls(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=_normalize_spatial(payload.get("width"), 832),
            height=_normalize_spatial(payload.get("height"), 1216),
            steps=max(1, int(payload.get("steps") or 28)),
            cfg=max(0.0, _float_value(payload.get("cfg"), 5.0)),
            seed=_int_value(payload.get("seed"), 42),
            sampler_name=str(
                payload.get("sampler_name") or payload.get("sampler") or "euler_ancestral"
            ).strip()
            or "euler_ancestral",
            scheduler=str(payload.get("scheduler") or "normal").strip() or "normal",
            checkpoint_name=checkpoint_name,
            clip_skip=max(1, _int_value(payload.get("clip_skip"), 1)),
            loras=_parse_loras(payload.get("loras")),
        )


def parse_sdxl_ipadapter_still_payload(
    payload: dict[str, Any] | None,
    *,
    default_prompt: str,
    default_checkpoint: str,
) -> tuple[SDXLIPAdapterRequest, tuple[str, ...]]:
    payload = payload or {}
    reference_images = _parse_reference_images(payload.get("reference_images"))

    merged_payload = dict(payload)
    still_generation = payload.get("still_generation")
    if isinstance(still_generation, dict):
        merged_payload.update(still_generation)
    if "checkpoint_name" not in merged_payload and merged_payload.get("checkpoint"):
        merged_payload["checkpoint_name"] = merged_payload["checkpoint"]
    if "sampler_name" not in merged_payload and merged_payload.get("sampler"):
        merged_payload["sampler_name"] = merged_payload["sampler"]
    if "denoise" not in merged_payload:
        # Still generation starts from an empty latent canvas rather than img2img latent reuse,
        # so the video-oriented low denoise default produces washed-out or nearly blank frames.
        merged_payload["denoise"] = 1.0

    request = SDXLIPAdapterRequest.from_payload(
        merged_payload,
        default_prompt=default_prompt,
        default_checkpoint=default_checkpoint,
    )
    return request, reference_images


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


def build_sdxl_still_workflow(
    *,
    request: SDXLStillRequest,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": request.checkpoint_name,
            },
        },
    }

    model_ref = ["1", 0]
    clip_ref = ["1", 1]
    next_node = 2

    for lora in request.loras:
        node_id = str(next_node)
        workflow[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": model_ref,
                "clip": clip_ref,
                "lora_name": lora["filename"],
                "strength_model": lora["strength"],
                "strength_clip": lora["strength"],
            },
        }
        model_ref = [node_id, 0]
        clip_ref = [node_id, 1]
        next_node += 1

    if request.clip_skip > 1:
        clip_skip_node = str(next_node)
        workflow[clip_skip_node] = {
            "class_type": "CLIPSetLastLayer",
            "inputs": {
                "stop_at_clip_layer": -request.clip_skip,
                "clip": clip_ref,
            },
        }
        clip_ref = [clip_skip_node, 0]
        next_node += 1

    positive_node = str(next_node)
    workflow[positive_node] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": request.prompt,
            "clip": clip_ref,
        },
    }
    next_node += 1

    negative_node = str(next_node)
    workflow[negative_node] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": request.negative_prompt,
            "clip": clip_ref,
        },
    }
    next_node += 1

    latent_node = str(next_node)
    workflow[latent_node] = {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": request.width,
            "height": request.height,
            "batch_size": 1,
        },
    }
    next_node += 1

    sampler_node = str(next_node)
    workflow[sampler_node] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_ref,
            "seed": request.seed,
            "steps": request.steps,
            "cfg": request.cfg,
            "sampler_name": request.sampler_name,
            "scheduler": request.scheduler,
            "positive": [positive_node, 0],
            "negative": [negative_node, 0],
            "latent_image": [latent_node, 0],
            "denoise": 1.0,
        },
    }
    next_node += 1

    decode_node = str(next_node)
    workflow[decode_node] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [sampler_node, 0],
            "vae": ["1", 2],
        },
    }
    next_node += 1

    save_node = str(next_node)
    workflow[save_node] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": [decode_node, 0],
            "filename_prefix": filename_prefix,
        },
    }
    return workflow, save_node


def build_sdxl_ipadapter_still_workflow(
    *,
    uploaded_image_names: list[str] | tuple[str, ...],
    request: SDXLIPAdapterRequest,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    image_names = tuple(str(item).strip() for item in uploaded_image_names if str(item).strip())
    if not image_names:
        raise ValueError("Still IPAdapter workflow requires at least one uploaded image")

    workflow: dict[str, Any] = {}
    next_node = 1

    checkpoint_node = str(next_node)
    workflow[checkpoint_node] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": request.checkpoint_name,
        },
    }
    next_node += 1

    model_ref: list[Any] = [checkpoint_node, 0]
    clip_ref: list[Any] = [checkpoint_node, 1]

    for lora in request.loras:
        lora_node = str(next_node)
        workflow[lora_node] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": model_ref,
                "clip": clip_ref,
                "lora_name": lora["filename"],
                "strength_model": lora["strength"],
                "strength_clip": lora["strength"],
            },
        }
        model_ref = [lora_node, 0]
        clip_ref = [lora_node, 1]
        next_node += 1

    if request.clip_skip > 1:
        clip_skip_node = str(next_node)
        workflow[clip_skip_node] = {
            "class_type": "CLIPSetLastLayer",
            "inputs": {
                "stop_at_clip_layer": -request.clip_skip,
                "clip": clip_ref,
            },
        }
        clip_ref = [clip_skip_node, 0]
        next_node += 1

    positive_node = str(next_node)
    workflow[positive_node] = {
        "class_type": "CLIPTextEncodeSDXL",
        "inputs": {
            "clip": clip_ref,
            "width": request.width,
            "height": request.height,
            "crop_w": 0,
            "crop_h": 0,
            "target_width": request.width,
            "target_height": request.height,
            "text_g": request.prompt,
            "text_l": request.prompt,
        },
    }
    next_node += 1

    negative_node = str(next_node)
    workflow[negative_node] = {
        "class_type": "CLIPTextEncodeSDXL",
        "inputs": {
            "clip": clip_ref,
            "width": request.width,
            "height": request.height,
            "crop_w": 0,
            "crop_h": 0,
            "target_width": request.width,
            "target_height": request.height,
            "text_g": request.negative_prompt,
            "text_l": request.negative_prompt,
        },
    }
    next_node += 1

    ipadapter_loader_node = str(next_node)
    workflow[ipadapter_loader_node] = {
        "class_type": "IPAdapterModelLoader",
        "inputs": {
            "ipadapter_file": request.ipadapter_file,
        },
    }
    next_node += 1

    clip_vision_loader_node = str(next_node)
    workflow[clip_vision_loader_node] = {
        "class_type": "CLIPVisionLoader",
        "inputs": {
            "clip_name": request.clip_vision_name,
        },
    }
    next_node += 1

    for image_name in image_names:
        load_node = str(next_node)
        workflow[load_node] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_name,
            },
        }
        next_node += 1

        adapter_node = str(next_node)
        workflow[adapter_node] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref,
                "ipadapter": [ipadapter_loader_node, 0],
                "image": [load_node, 0],
                "weight": request.ipadapter_weight,
                "weight_type": request.ipadapter_weight_type,
                "combine_embeds": "concat",
                "start_at": request.ipadapter_start_at,
                "end_at": request.ipadapter_end_at,
                "embeds_scaling": request.embeds_scaling,
                "clip_vision": [clip_vision_loader_node, 0],
            },
        }
        model_ref = [adapter_node, 0]
        next_node += 1

    latent_node = str(next_node)
    workflow[latent_node] = {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": request.width,
            "height": request.height,
            "batch_size": 1,
        },
    }
    next_node += 1

    sampler_node = str(next_node)
    workflow[sampler_node] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_ref,
            "seed": request.seed,
            "steps": request.steps,
            "cfg": request.cfg,
            "sampler_name": request.sampler_name,
            "scheduler": request.scheduler,
            "positive": [positive_node, 0],
            "negative": [negative_node, 0],
            "latent_image": [latent_node, 0],
            "denoise": request.denoise,
        },
    }
    next_node += 1

    decode_node = str(next_node)
    workflow[decode_node] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [sampler_node, 0],
            "vae": [checkpoint_node, 2],
        },
    }
    next_node += 1

    save_node = str(next_node)
    workflow[save_node] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": [decode_node, 0],
            "filename_prefix": filename_prefix,
        },
    }
    return workflow, save_node


def build_sdxl_ipadapter_still_repair_workflow(
    *,
    uploaded_source_image_name: str,
    uploaded_reference_image_names: list[str] | tuple[str, ...],
    request: SDXLIPAdapterRequest,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    source_image_name = str(uploaded_source_image_name).strip()
    if not source_image_name:
        raise ValueError("Repair workflow requires an uploaded source image")
    reference_image_names = tuple(
        str(item).strip() for item in uploaded_reference_image_names if str(item).strip()
    )
    if not reference_image_names:
        raise ValueError("Repair workflow requires at least one uploaded reference image")

    workflow: dict[str, Any] = {}
    next_node = 1

    checkpoint_node = str(next_node)
    workflow[checkpoint_node] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": request.checkpoint_name,
        },
    }
    next_node += 1

    model_ref: list[Any] = [checkpoint_node, 0]
    clip_ref: list[Any] = [checkpoint_node, 1]

    positive_node = str(next_node)
    workflow[positive_node] = {
        "class_type": "CLIPTextEncodeSDXL",
        "inputs": {
            "clip": clip_ref,
            "width": request.width,
            "height": request.height,
            "crop_w": 0,
            "crop_h": 0,
            "target_width": request.width,
            "target_height": request.height,
            "text_g": request.prompt,
            "text_l": request.prompt,
        },
    }
    next_node += 1

    negative_node = str(next_node)
    workflow[negative_node] = {
        "class_type": "CLIPTextEncodeSDXL",
        "inputs": {
            "clip": clip_ref,
            "width": request.width,
            "height": request.height,
            "crop_w": 0,
            "crop_h": 0,
            "target_width": request.width,
            "target_height": request.height,
            "text_g": request.negative_prompt,
            "text_l": request.negative_prompt,
        },
    }
    next_node += 1

    ipadapter_loader_node = str(next_node)
    workflow[ipadapter_loader_node] = {
        "class_type": "IPAdapterModelLoader",
        "inputs": {
            "ipadapter_file": request.ipadapter_file,
        },
    }
    next_node += 1

    clip_vision_loader_node = str(next_node)
    workflow[clip_vision_loader_node] = {
        "class_type": "CLIPVisionLoader",
        "inputs": {
            "clip_name": request.clip_vision_name,
        },
    }
    next_node += 1

    source_node = str(next_node)
    workflow[source_node] = {
        "class_type": "LoadImage",
        "inputs": {
            "image": source_image_name,
        },
    }
    next_node += 1

    for image_name in reference_image_names:
        load_node = str(next_node)
        workflow[load_node] = {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_name,
            },
        }
        next_node += 1

        adapter_node = str(next_node)
        workflow[adapter_node] = {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": model_ref,
                "ipadapter": [ipadapter_loader_node, 0],
                "image": [load_node, 0],
                "weight": request.repair_strength,
                "weight_type": request.ipadapter_weight_type,
                "combine_embeds": "concat",
                "start_at": request.ipadapter_start_at,
                "end_at": request.ipadapter_end_at,
                "embeds_scaling": request.embeds_scaling,
                "clip_vision": [clip_vision_loader_node, 0],
            },
        }
        model_ref = [adapter_node, 0]
        next_node += 1

    latent_node = str(next_node)
    workflow[latent_node] = {
        "class_type": "VAEEncode",
        "inputs": {
            "pixels": [source_node, 0],
            "vae": [checkpoint_node, 2],
        },
    }
    next_node += 1

    sampler_node = str(next_node)
    workflow[sampler_node] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_ref,
            "seed": request.seed,
            "steps": request.steps,
            "cfg": request.cfg,
            "sampler_name": request.sampler_name,
            "scheduler": request.scheduler,
            "positive": [positive_node, 0],
            "negative": [negative_node, 0],
            "latent_image": [latent_node, 0],
            "denoise": request.repair_denoise,
        },
    }
    next_node += 1

    decode_node = str(next_node)
    workflow[decode_node] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [sampler_node, 0],
            "vae": [checkpoint_node, 2],
        },
    }
    next_node += 1

    save_node = str(next_node)
    workflow[save_node] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": [decode_node, 0],
            "filename_prefix": filename_prefix,
        },
    }
    return workflow, save_node


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
