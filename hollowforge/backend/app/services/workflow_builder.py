"""Dynamic ComfyUI workflow builder supporting 0..N LoRAs."""

from __future__ import annotations

from typing import Any

from app.services.workflow_registry import (
    get_workflow_lane_spec,
    resolve_workflow_lane,
)

QUALITY_UPSCALE_REQUIRED_NODES: tuple[str, ...] = (
    "LoadImage",
    "ImageScale",
    "UpscaleModelLoader",
    "ImageUpscaleWithModel",
    "CheckpointLoaderSimple",
    "CLIPTextEncodeSDXL",
    "VAEEncode",
    "KSampler",
    "VAEDecode",
    "SaveImage",
)

GENERAL_QUALITY_UPSCALE_REQUIRED_NODES: tuple[str, ...] = (
    "LoadImage",
    "ImageScale",
    "UpscaleModelLoader",
    "ImageUpscaleWithModel",
    "SaveImage",
)


def compute_quality_redraw_dimensions(
    width: int,
    height: int,
    *,
    max_side: int = 1024,
    multiple: int = 64,
) -> tuple[int, int]:
    """Clamp redraw resolution for MPS stability while preserving aspect ratio."""
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if multiple <= 0:
        raise ValueError("multiple must be positive")

    scale = min(1.0, max_side / max(width, height))
    target_w = max(multiple, int((width * scale) // multiple) * multiple)
    target_h = max(multiple, int((height * scale) // multiple) * multiple)

    # Avoid collapsing to an invalid 0-sized dimension on narrow inputs.
    if target_w == 0:
        target_w = multiple
    if target_h == 0:
        target_h = multiple

    return target_w, target_h


def compute_general_quality_dimensions(
    width: int,
    height: int,
    *,
    pre_scale: float = 1.1,
    max_side: int = 1344,
    multiple: int = 64,
    final_scale: float = 4.0,
) -> tuple[int, int, int, int]:
    """Plan a checkpoint-independent deterministic quality path.

    The realistic/general branch avoids latent redraw entirely. Instead it
    applies a small Lanczos pre-scale before model upscaling, then normalizes
    back to an exact final size. This keeps the workflow stable even when the
    original checkpoint is unavailable in the current ComfyUI runtime.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if pre_scale <= 0:
        raise ValueError("pre_scale must be positive")
    if multiple <= 0:
        raise ValueError("multiple must be positive")
    if final_scale <= 0:
        raise ValueError("final_scale must be positive")

    scaled_w = max(width, int(width * pre_scale))
    scaled_h = max(height, int(height * pre_scale))

    pre_w, pre_h = compute_quality_redraw_dimensions(
        scaled_w,
        scaled_h,
        max_side=max_side,
        multiple=multiple,
    )

    final_w = max(1, int(round(width * final_scale)))
    final_h = max(1, int(round(height * final_scale)))
    return pre_w, pre_h, final_w, final_h


def select_quality_workflow_strategy(
    checkpoint_profile: str,
    *,
    checkpoint_available: bool,
) -> str:
    """Choose which quality workflow branch should run for a checkpoint."""
    if checkpoint_profile == "anime-illustration" and checkpoint_available:
        return "latent_redraw"
    return "deterministic_clean"


def build_workflow(
    checkpoint: str,
    loras: list[tuple[str, float]],
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    steps: int = 28,
    cfg: float = 7.0,
    width: int = 832,
    height: int = 1216,
    sampler: str = "euler",
    scheduler: str = "normal",
    clip_skip: int | None = None,
    filename_prefix: str = "hollowforge",
    workflow_lane: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Build a workflow with a variable-length LoRA chain.

    Returns (workflow_dict, save_node_id).
    """
    lane = resolve_workflow_lane(checkpoint, workflow_lane)
    if lane == "sdxl_illustrious":
        return _build_sdxl_illustrious_workflow(
            checkpoint=checkpoint,
            loras=loras,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            steps=steps,
            cfg=cfg,
            width=width,
            height=height,
            sampler=sampler,
            scheduler=scheduler,
            clip_skip=clip_skip,
            filename_prefix=filename_prefix,
        )
    return _build_classic_clip_workflow(
        checkpoint=checkpoint,
        loras=loras,
        positive_prompt=positive_prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        steps=steps,
        cfg=cfg,
        width=width,
        height=height,
        sampler=sampler,
        scheduler=scheduler,
        clip_skip=clip_skip,
        filename_prefix=filename_prefix,
    )


def _attach_checkpoint_and_loras(
    workflow: dict[str, Any],
    checkpoint: str,
    loras: list[tuple[str, float]],
    *,
    start_id: int = 1,
) -> tuple[int, str, tuple[str, int], tuple[str, int]]:
    ckpt_id = str(start_id)
    workflow[ckpt_id] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }
    next_id = start_id + 1
    model_source = (ckpt_id, 0)
    clip_source = (ckpt_id, 1)

    for lora_name, strength in loras:
        lora_id = str(next_id)
        workflow[lora_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_name,
                "strength_model": strength,
                "strength_clip": strength,
                "model": [model_source[0], model_source[1]],
                "clip": [clip_source[0], clip_source[1]],
            },
        }
        model_source = (lora_id, 0)
        clip_source = (lora_id, 1)
        next_id += 1

    return next_id, ckpt_id, model_source, clip_source


def _maybe_attach_clip_skip(
    workflow: dict[str, Any],
    clip_source: tuple[str, int],
    clip_skip: int | None,
    *,
    next_id: int,
) -> tuple[int, tuple[str, int]]:
    if clip_skip is None:
        return next_id, clip_source

    clip_skip_id = str(next_id)
    workflow[clip_skip_id] = {
        "class_type": "CLIPSetLastLayer",
        "inputs": {
            "stop_at_clip_layer": -clip_skip,
            "clip": [clip_source[0], clip_source[1]],
        },
    }
    return next_id + 1, (clip_skip_id, 0)


def _attach_classic_text_encode(
    workflow: dict[str, Any],
    text: str,
    clip_source: tuple[str, int],
    *,
    next_id: int,
) -> tuple[int, str]:
    node_id = str(next_id)
    workflow[node_id] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": text,
            "clip": [clip_source[0], clip_source[1]],
        },
    }
    return next_id + 1, node_id


def _attach_sdxl_text_encode(
    workflow: dict[str, Any],
    text: str,
    clip_source: tuple[str, int],
    *,
    width: int,
    height: int,
    next_id: int,
) -> tuple[int, str]:
    node_id = str(next_id)
    workflow[node_id] = {
        "class_type": "CLIPTextEncodeSDXL",
        "inputs": {
            "clip": [clip_source[0], clip_source[1]],
            "width": width,
            "height": height,
            "crop_w": 0,
            "crop_h": 0,
            "target_width": width,
            "target_height": height,
            "text_g": text,
            "text_l": text,
        },
    }
    return next_id + 1, node_id


def _build_classic_clip_workflow(
    checkpoint: str,
    loras: list[tuple[str, float]],
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    steps: int,
    cfg: float,
    width: int,
    height: int,
    sampler: str,
    scheduler: str,
    clip_skip: int | None,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    workflow: dict[str, Any] = {}
    next_id, ckpt_id, model_source, clip_source = _attach_checkpoint_and_loras(
        workflow,
        checkpoint,
        loras,
    )
    next_id, clip_source = _maybe_attach_clip_skip(
        workflow,
        clip_source,
        clip_skip,
        next_id=next_id,
    )
    next_id, pos_id = _attach_classic_text_encode(
        workflow,
        positive_prompt,
        clip_source,
        next_id=next_id,
    )
    next_id, neg_id = _attach_classic_text_encode(
        workflow,
        negative_prompt,
        clip_source,
        next_id=next_id,
    )

    # --- Empty latent image ---
    latent_id = str(next_id)
    workflow[latent_id] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": width, "height": height, "batch_size": 1},
    }
    next_id += 1

    # --- KSampler ---
    sampler_id = str(next_id)
    workflow[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": 1.0,
            "model": [model_source[0], model_source[1]],
            "positive": [pos_id, 0],
            "negative": [neg_id, 0],
            "latent_image": [latent_id, 0],
        },
    }
    next_id += 1

    # --- VAE decode ---
    vae_id = str(next_id)
    workflow[vae_id] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [sampler_id, 0],
            "vae": [ckpt_id, 2],
        },
    }
    next_id += 1

    # --- Save image ---
    save_id = str(next_id)
    workflow[save_id] = {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": filename_prefix,
            "images": [vae_id, 0],
        },
    }

    return workflow, save_id


def _build_sdxl_illustrious_workflow(
    checkpoint: str,
    loras: list[tuple[str, float]],
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    steps: int,
    cfg: float,
    width: int,
    height: int,
    sampler: str,
    scheduler: str,
    clip_skip: int | None,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    workflow: dict[str, Any] = {}
    lane_spec = get_workflow_lane_spec("sdxl_illustrious")
    resolved_clip_skip = clip_skip if clip_skip is not None else lane_spec.defaults["clip_skip"]

    next_id, ckpt_id, model_source, clip_source = _attach_checkpoint_and_loras(
        workflow,
        checkpoint,
        loras,
    )
    next_id, clip_source = _maybe_attach_clip_skip(
        workflow,
        clip_source,
        resolved_clip_skip,
        next_id=next_id,
    )
    next_id, pos_id = _attach_sdxl_text_encode(
        workflow,
        positive_prompt,
        clip_source,
        width=width,
        height=height,
        next_id=next_id,
    )
    next_id, neg_id = _attach_sdxl_text_encode(
        workflow,
        negative_prompt,
        clip_source,
        width=width,
        height=height,
        next_id=next_id,
    )

    latent_id = str(next_id)
    workflow[latent_id] = {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": width, "height": height, "batch_size": 1},
    }
    next_id += 1

    sampler_id = str(next_id)
    workflow[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": 1.0,
            "model": [model_source[0], model_source[1]],
            "positive": [pos_id, 0],
            "negative": [neg_id, 0],
            "latent_image": [latent_id, 0],
        },
    }
    next_id += 1

    vae_id = str(next_id)
    workflow[vae_id] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [sampler_id, 0],
            "vae": [ckpt_id, 2],
        },
    }
    next_id += 1

    save_id = str(next_id)
    workflow[save_id] = {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": filename_prefix,
            "images": [vae_id, 0],
        },
    }
    return workflow, save_id


def build_upscale_workflow(
    image_filename: str,
    upscale_model: str = "remacri_original.safetensors",
    filename_prefix: str = "hollowforge_upscaled",
) -> tuple[dict[str, Any], str]:
    """Build the deterministic safe upscale workflow.

    Returns (workflow_dict, save_node_id).
    """
    workflow = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_filename,
                "upload": "image",
            },
        },
        "2": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": upscale_model},
        },
        "3": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["2", 0],
                "image": ["1", 0],
            },
        },
        "4": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": filename_prefix,
                "images": ["3", 0],
            },
        },
    }
    return workflow, "4"


def build_quality_upscale_workflow(
    image_filename: str,
    upscale_model: str = "remacri_original.safetensors",
    checkpoint: str = "waiIllustriousSDXL_v160.safetensors",
    positive_prompt: str = "",
    negative_prompt: str = "",
    denoise: float = 0.18,
    steps: int = 12,
    cfg: float = 5.5,
    seed: int = 42,
    redraw_width: int = 704,
    redraw_height: int = 1024,
    filename_prefix: str = "hollowforge_upscaled_quality",
    clip_skip: int | None = None,
) -> tuple[dict[str, Any], str]:
    """Build a staged quality workflow.

    Stage A: low-denoise latent detail recovery at source resolution
    Stage B: deterministic model upscale
    """
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_filename,
                "upload": "image",
            },
        },
        "2": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["1", 0],
                "upscale_method": "lanczos",
                "width": redraw_width,
                "height": redraw_height,
                "crop": "disabled",
            },
        },
    }
    lane = resolve_workflow_lane(checkpoint)
    lane_spec = get_workflow_lane_spec(lane)
    workflow["3"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }

    next_id = 4
    clip_source: tuple[str, int] = ("3", 1)
    resolved_clip_skip = clip_skip if clip_skip is not None else lane_spec.defaults["clip_skip"]
    if resolved_clip_skip is not None:
        workflow[str(next_id)] = {
            "class_type": "CLIPSetLastLayer",
            "inputs": {
                "stop_at_clip_layer": -resolved_clip_skip,
                "clip": ["3", 1],
            },
        }
        clip_source = (str(next_id), 0)
        next_id += 1

    if lane == "sdxl_illustrious":
        next_id, pos_id = _attach_sdxl_text_encode(
            workflow,
            positive_prompt,
            clip_source,
            width=redraw_width,
            height=redraw_height,
            next_id=next_id,
        )
        next_id, neg_id = _attach_sdxl_text_encode(
            workflow,
            negative_prompt,
            clip_source,
            width=redraw_width,
            height=redraw_height,
            next_id=next_id,
        )
    else:
        next_id, pos_id = _attach_classic_text_encode(
            workflow,
            positive_prompt,
            clip_source,
            next_id=next_id,
        )
        next_id, neg_id = _attach_classic_text_encode(
            workflow,
            negative_prompt,
            clip_source,
            next_id=next_id,
        )

    latent_id = str(next_id)
    workflow[latent_id] = {
        "class_type": "VAEEncode",
        "inputs": {
            "pixels": ["2", 0],
            "vae": ["3", 2],
        },
    }
    next_id += 1

    sampler_id = str(next_id)
    workflow[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": lane_spec.defaults["sampler"],
            "scheduler": lane_spec.defaults["scheduler"],
            "denoise": denoise,
            "model": ["3", 0],
            "positive": [pos_id, 0],
            "negative": [neg_id, 0],
            "latent_image": [latent_id, 0],
        },
    }
    next_id += 1

    decode_id = str(next_id)
    workflow[decode_id] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [sampler_id, 0],
            "vae": ["3", 2],
        },
    }
    next_id += 1

    upscale_loader_id = str(next_id)
    workflow[upscale_loader_id] = {
        "class_type": "UpscaleModelLoader",
        "inputs": {"model_name": upscale_model},
    }
    next_id += 1

    upscale_id = str(next_id)
    workflow[upscale_id] = {
        "class_type": "ImageUpscaleWithModel",
        "inputs": {
            "upscale_model": [upscale_loader_id, 0],
            "image": [decode_id, 0],
        },
    }
    next_id += 1

    save_id = str(next_id)
    workflow[save_id] = {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": filename_prefix,
            "images": [upscale_id, 0],
        },
    }
    return workflow, save_id


def build_general_quality_upscale_workflow(
    image_filename: str,
    upscale_model: str = "realesr-general-x4v3.pth",
    pre_width: int = 896,
    pre_height: int = 1280,
    final_width: int = 3328,
    final_height: int = 4864,
    filename_prefix: str = "hollowforge_upscaled_quality_general",
) -> tuple[dict[str, Any], str]:
    """Build a checkpoint-independent quality workflow for realistic images.

    This branch avoids latent redraw and relies only on deterministic image
    operators that are stable across mixed checkpoint families.
    """
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": image_filename,
                "upload": "image",
            },
        },
        "2": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["1", 0],
                "upscale_method": "lanczos",
                "width": pre_width,
                "height": pre_height,
                "crop": "disabled",
            },
        },
        "3": {
            "class_type": "UpscaleModelLoader",
            "inputs": {"model_name": upscale_model},
        },
        "4": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["3", 0],
                "image": ["2", 0],
            },
        },
        "5": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["4", 0],
                "upscale_method": "lanczos",
                "width": final_width,
                "height": final_height,
                "crop": "disabled",
            },
        },
        "6": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": filename_prefix,
                "images": ["5", 0],
            },
        },
    }
    return workflow, "6"


def build_adetail_workflow(
    source_image_filename: str,
    mask_image_filename: str,
    checkpoint: str,
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    denoise: float = 0.4,
    steps: int = 20,
    cfg: float = 7.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    filename_prefix: str = "hollowforge_adetail",
) -> tuple[dict[str, Any], str]:
    """Build a ComfyUI inpainting workflow for face detail fix."""
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": source_image_filename,
                "upload": "image",
            },
        },
        "2": {
            "class_type": "LoadImageMask",
            "inputs": {
                "image": mask_image_filename,
                "channel": "red",
            },
        },
        "3": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive_prompt, "clip": ["3", 1]},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["3", 1]},
        },
        "6": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {
                "pixels": ["1", 0],
                "vae": ["3", 2],
                "mask": ["2", 0],
                "grow_mask_by": 6,
            },
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": denoise,
                "model": ["3", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 2],
            },
        },
        "10": {
            "class_type": "SaveImage",
            "inputs": {
                "filename_prefix": filename_prefix,
                "images": ["8", 0],
            },
        },
    }
    return workflow, "10"


def build_hiresfix_workflow(
    source_image_filename: str,
    checkpoint: str,
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    upscale_factor: float = 1.5,
    denoise: float = 0.5,
    steps: int = 20,
    cfg: float = 7.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    filename_prefix: str = "hollowforge_hiresfix",
    clip_skip: int | None = None,
) -> tuple[dict[str, Any], str]:
    """Latent upscale + second KSampler pass (Hires.fix)."""
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": source_image_filename,
                "upload": "image",
            },
        },
    }
    lane = resolve_workflow_lane(checkpoint)
    lane_spec = get_workflow_lane_spec(lane)
    workflow["2"] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }

    next_id = 3
    clip_source: tuple[str, int] = ("2", 1)
    resolved_clip_skip = clip_skip if clip_skip is not None else lane_spec.defaults["clip_skip"]
    if resolved_clip_skip is not None:
        workflow[str(next_id)] = {
            "class_type": "CLIPSetLastLayer",
            "inputs": {
                "stop_at_clip_layer": -resolved_clip_skip,
                "clip": ["2", 1],
            },
        }
        clip_source = (str(next_id), 0)
        next_id += 1

    target_width = max(256, int(round(lane_spec.defaults["width"] * upscale_factor)))
    target_height = max(256, int(round(lane_spec.defaults["height"] * upscale_factor)))
    if lane == "sdxl_illustrious":
        next_id, pos_id = _attach_sdxl_text_encode(
            workflow,
            positive_prompt,
            clip_source,
            width=target_width,
            height=target_height,
            next_id=next_id,
        )
        next_id, neg_id = _attach_sdxl_text_encode(
            workflow,
            negative_prompt,
            clip_source,
            width=target_width,
            height=target_height,
            next_id=next_id,
        )
    else:
        next_id, pos_id = _attach_classic_text_encode(
            workflow,
            positive_prompt,
            clip_source,
            next_id=next_id,
        )
        next_id, neg_id = _attach_classic_text_encode(
            workflow,
            negative_prompt,
            clip_source,
            next_id=next_id,
        )

    vae_encode_id = str(next_id)
    workflow[vae_encode_id] = {
        "class_type": "VAEEncode",
        "inputs": {
            "pixels": ["1", 0],
            "vae": ["2", 2],
        },
    }
    next_id += 1

    latent_upscale_id = str(next_id)
    workflow[latent_upscale_id] = {
        "class_type": "LatentUpscaleBy",
        "inputs": {
            "samples": [vae_encode_id, 0],
            "upscale_method": "nearest-exact",
            "scale_by": upscale_factor,
        },
    }
    next_id += 1

    sampler_id = str(next_id)
    workflow[sampler_id] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,
            "scheduler": scheduler,
            "denoise": denoise,
            "model": ["2", 0],
            "positive": [pos_id, 0],
            "negative": [neg_id, 0],
            "latent_image": [latent_upscale_id, 0],
        },
    }
    next_id += 1

    decode_id = str(next_id)
    workflow[decode_id] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": [sampler_id, 0],
            "vae": ["2", 2],
        },
    }
    next_id += 1

    save_id = str(next_id)
    workflow[save_id] = {
        "class_type": "SaveImage",
        "inputs": {
            "images": [decode_id, 0],
            "filename_prefix": filename_prefix,
        },
    }
    return workflow, save_id
