"""Dynamic ComfyUI workflow builder supporting 0..N LoRAs."""

from __future__ import annotations

from typing import Any


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
) -> tuple[dict[str, Any], str]:
    """Build an SDXL workflow with a variable-length LoRA chain.

    Returns (workflow_dict, save_node_id).
    """
    workflow: dict[str, Any] = {}
    next_id = 1

    # --- Checkpoint loader (node 1) ---
    ckpt_id = str(next_id)
    workflow[ckpt_id] = {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": checkpoint},
    }
    next_id += 1

    # Track the current model/clip source node
    model_source = (ckpt_id, 0)
    clip_source = (ckpt_id, 1)

    # --- LoRA loaders ---
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

    # Optional clip skip via CLIPSetLastLayer wrapper.
    if clip_skip is not None:
        clip_skip_id = str(next_id)
        workflow[clip_skip_id] = {
            "class_type": "CLIPSetLastLayer",
            "inputs": {
                "stop_at_clip_layer": -clip_skip,
                "clip": [clip_source[0], clip_source[1]],
            },
        }
        clip_source = (clip_skip_id, 0)
        next_id += 1

    # --- CLIP text encode (positive) ---
    pos_id = str(next_id)
    workflow[pos_id] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": positive_prompt,
            "clip": [clip_source[0], clip_source[1]],
        },
    }
    next_id += 1

    # --- CLIP text encode (negative) ---
    neg_id = str(next_id)
    workflow[neg_id] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": negative_prompt,
            "clip": [clip_source[0], clip_source[1]],
        },
    }
    next_id += 1

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


def build_upscale_workflow(
    image_path: str,
    upscale_model: str = "remacri_original.safetensors",
    filename_prefix: str = "hollowforge_upscaled",
) -> tuple[dict[str, Any], str]:
    """Build an image-only upscale workflow.

    Returns (workflow_dict, save_node_id).
    """
    workflow: dict[str, Any] = {}
    next_id = 1

    # --- Load source image ---
    load_id = str(next_id)
    workflow[load_id] = {
        "class_type": "LoadImage",
        "inputs": {
            "image": image_path,
        },
    }
    next_id += 1

    # --- Load upscale model ---
    model_id = str(next_id)
    workflow[model_id] = {
        "class_type": "UpscaleModelLoader",
        "inputs": {
            "model_name": upscale_model,
        },
    }
    next_id += 1

    # --- Upscale ---
    upscale_id = str(next_id)
    workflow[upscale_id] = {
        "class_type": "ImageUpscaleWithModel",
        "inputs": {
            "upscale_model": [model_id, 0],
            "image": [load_id, 0],
        },
    }
    next_id += 1

    # --- Save ---
    save_id = str(next_id)
    workflow[save_id] = {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": filename_prefix,
            "images": [upscale_id, 0],
        },
    }

    return workflow, save_id
