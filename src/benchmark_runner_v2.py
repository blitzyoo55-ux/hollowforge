#!/usr/bin/env python3
"""ComfyUI benchmark runner v2 for WAI Illustrious + multi-LoRA matrix.

- HTTP polling only (/prompt + /history)
- 2 artist sets x 5 series x 2 runs = 20 images
- Downloads finished image to local benchmark_v2 folder
"""

from __future__ import annotations

import random
import time
import uuid
from pathlib import Path
from typing import Any

import requests

COMFY_BASE_URL = "http://127.0.0.1:8188"
OUTPUT_DIR = Path(
    "/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/data/benchmark_v2/"
)

CHECKPOINT_NAME = "waiIllustriousSDXL_v160.safetensors"
WIDTH = 832
HEIGHT = 1216
STEPS = 28
CFG = 7.0
SAMPLER_NAME = "euler"
SCHEDULER = "normal"

QUALITY_PREFIX = "masterpiece, best quality, ultra detailed, absurdres, highres"
NEGATIVE_PROMPT = (
    "child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, "
    "bad hands, extra fingers, extra digits, malformed limbs, deformed face, text, logo, "
    "watermark, jpeg artifacts, mosaic censoring, censored, bar censor, light censor, censoring"
)

SERIES_PROMPTS: dict[str, str] = {
    "A": (
        "{quality}, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, "
        "beautiful detailed eyes, expressive eyes, thick eyelashes, glossy latex catsuit, "
        "full body latex, full-face gas mask, sealed mask, faceless, orange accent straps, "
        "black bodysuit, laboratory, white tile wall, scientific equipment, standing, full body, "
        "cinematic rim light, dramatic shadows, high contrast, fetish fashion editorial"
    ),
    "B": (
        "{quality}, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, "
        "beautiful detailed eyes, intense eye contact, half mask, mouth covered, visible eyes only, "
        "glossy latex catsuit, full body latex, black and orange palette, concrete dungeon, kneeling, "
        "cowboy shot, hard studio light, moody atmosphere, fetish editorial"
    ),
    "C": (
        "{quality}, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, "
        "beautiful detailed eyes, ball gag, blindfold, restrained aesthetic, glossy latex catsuit, "
        "black latex straps, harness, orange neon light, cyberpunk neon street, rain, standing, "
        "full body, neon backlight, dramatic mood, fetish editorial"
    ),
    "D": (
        "{quality}, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, "
        "beautiful detailed eyes, kigurumi mask, expressionless doll face mask, glossy latex catsuit, "
        "black and orange accents, concrete dungeon, kneeling, full body, spotlight, surreal fashion, "
        "clean composition"
    ),
    "E": (
        "{quality}, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, "
        "full latex hood, completely covered head, no hair visible, faceless, glossy latex catsuit, "
        "black latex shine, orange reflected light, laboratory, white tile wall, standing, "
        "low angle full body, cinematic rim light, atmospheric haze, fetish fashion editorial"
    ),
}

SERIES_LORA_4TH: dict[str, tuple[str, float]] = {
    "A": ("Proper_Latex_Catsuit.safetensors", 0.6),
    "B": ("Proper_Latex_Catsuit.safetensors", 0.5),
    "C": ("Harness_Panel_Gag_IL.safetensors", 0.7),
    "D": ("latex_huger_c7-1+76-1+64-4.safetensors", 0.5),
    "E": ("Proper_Latex_Catsuit.safetensors", 0.7),
}

ARTIST_SETS: dict[str, tuple[str, float]] = {
    "incase": ("incase_new_style_red_ill.safetensors", 0.7),
    "ickpot": ("IckpotIXL_v1.safetensors", 0.7),
}

EYE_LORA = ("DetailedEyes_V3.safetensors", 0.5)
LATEX_LORA = ("Shiny_Clothes_and_Skin_Latex_Illustrious.safetensors", 0.6)


def build_workflow(
    checkpoint_name: str,
    loras: list[tuple[str, float]],
    positive_prompt: str,
    negative_prompt: str,
    seed: int,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    """Build SDXL workflow with fixed 4x LoRA chain."""

    if len(loras) != 4:
        raise ValueError(f"Expected exactly 4 LoRAs, got {len(loras)}")

    workflow: dict[str, Any] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        },
        "2": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": loras[0][0],
                "strength_model": loras[0][1],
                "strength_clip": loras[0][1],
                "model": ["1", 0],
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": loras[1][0],
                "strength_model": loras[1][1],
                "strength_clip": loras[1][1],
                "model": ["2", 0],
                "clip": ["2", 1],
            },
        },
        "4": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": loras[2][0],
                "strength_model": loras[2][1],
                "strength_clip": loras[2][1],
                "model": ["3", 0],
                "clip": ["3", 1],
            },
        },
        "5": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": loras[3][0],
                "strength_model": loras[3][1],
                "strength_clip": loras[3][1],
                "model": ["4", 0],
                "clip": ["4", 1],
            },
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive_prompt, "clip": ["5", 1]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["5", 1]},
        },
        "8": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1},
        },
        "9": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": STEPS,
                "cfg": CFG,
                "sampler_name": SAMPLER_NAME,
                "scheduler": SCHEDULER,
                "denoise": 1.0,
                "model": ["5", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["8", 0],
            },
        },
        "10": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["9", 0], "vae": ["1", 2]},
        },
        "11": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": filename_prefix, "images": ["10", 0]},
        },
    }
    return workflow, "11"


def submit_prompt(session: requests.Session, workflow: dict[str, Any]) -> str:
    payload = {"prompt": workflow, "client_id": f"benchmark_runner_v2_{uuid.uuid4()}"}
    response = session.post(f"{COMFY_BASE_URL}/prompt", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"Missing prompt_id in /prompt response: {data}")
    return prompt_id


def fetch_history_entry(session: requests.Session, prompt_id: str) -> dict[str, Any] | None:
    response = session.get(f"{COMFY_BASE_URL}/history/{prompt_id}", timeout=30)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict):
            if prompt_id in data:
                return data[prompt_id]
            if data:
                return next(iter(data.values()))

    response = session.get(f"{COMFY_BASE_URL}/history", timeout=30)
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict):
        return data.get(prompt_id)
    return None


def wait_for_completion(
    session: requests.Session,
    prompt_id: str,
    save_node_id: str,
    timeout_sec: int = 900,
    poll_interval_sec: float = 1.0,
) -> list[dict[str, Any]]:
    start = time.perf_counter()
    while True:
        if time.perf_counter() - start > timeout_sec:
            raise TimeoutError(f"Timeout waiting for completion. prompt_id={prompt_id}")

        entry = fetch_history_entry(session, prompt_id)
        if entry:
            status = entry.get("status", {})
            if isinstance(status, dict):
                messages = status.get("messages", [])
                for msg in messages:
                    if isinstance(msg, list) and len(msg) >= 2 and msg[0] == "execution_error":
                        raise RuntimeError(f"ComfyUI execution_error: {msg[1]}")

            outputs = entry.get("outputs", {})
            node_output = outputs.get(save_node_id, {}) if isinstance(outputs, dict) else {}
            images = node_output.get("images", []) if isinstance(node_output, dict) else []
            if images:
                return images

        time.sleep(poll_interval_sec)


def download_image(session: requests.Session, image_info: dict[str, Any], output_path: Path) -> None:
    params = {
        "filename": image_info.get("filename", ""),
        "subfolder": image_info.get("subfolder", ""),
        "type": image_info.get("type", "output"),
    }
    response = session.get(f"{COMFY_BASE_URL}/view", params=params, timeout=60)
    response.raise_for_status()
    output_path.write_bytes(response.content)


def build_positive_prompt(series_key: str) -> str:
    template = SERIES_PROMPTS.get(series_key)
    if not template:
        raise ValueError(f"Unknown series key: {series_key}")
    return template.format(quality=QUALITY_PREFIX)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    try:
        health = session.get(f"{COMFY_BASE_URL}/system_stats", timeout=10)
        health.raise_for_status()
    except requests.RequestException as exc:
        raise SystemExit(f"Failed to connect to ComfyUI at {COMFY_BASE_URL}: {exc}") from exc

    total_jobs = len(ARTIST_SETS) * len(SERIES_PROMPTS) * 2
    print("=== ComfyUI Benchmark Runner v2 ===", flush=True)
    print(f"Server: {COMFY_BASE_URL}", flush=True)
    print(f"Output directory: {OUTPUT_DIR}", flush=True)
    print(f"Checkpoint: {CHECKPOINT_NAME}", flush=True)
    print(f"Total jobs: {total_jobs}", flush=True)

    overall_start = time.perf_counter()
    success_count = 0
    fail_count = 0
    job_index = 0

    for artist_key, artist_lora in ARTIST_SETS.items():
        for series_key in ["A", "B", "C", "D", "E"]:
            for n in [1, 2]:
                job_index += 1
                filename = f"benchmark_v2_{artist_key}_{series_key}_{n}.png"
                out_file = OUTPUT_DIR / filename
                seed = random.randint(0, 2**31 - 1)

                fourth_lora = SERIES_LORA_4TH[series_key]
                lora_chain = [artist_lora, EYE_LORA, LATEX_LORA, fourth_lora]
                positive_prompt = build_positive_prompt(series_key)

                workflow, save_node_id = build_workflow(
                    checkpoint_name=CHECKPOINT_NAME,
                    loras=lora_chain,
                    positive_prompt=positive_prompt,
                    negative_prompt=NEGATIVE_PROMPT,
                    seed=seed,
                    filename_prefix=filename.removesuffix(".png"),
                )

                print(
                    (
                        f"[{job_index}/{total_jobs}] START artist={artist_key} series={series_key} "
                        f"run={n} seed={seed} file={filename}"
                    ),
                    flush=True,
                )

                case_start = time.perf_counter()
                try:
                    prompt_id = submit_prompt(session, workflow)
                    images = wait_for_completion(session, prompt_id, save_node_id)
                    download_image(session, images[0], out_file)
                    elapsed = time.perf_counter() - case_start
                    success_count += 1
                    print(
                        f"[{job_index}/{total_jobs}] DONE {out_file} ({elapsed:.2f}s)",
                        flush=True,
                    )
                except Exception as exc:
                    elapsed = time.perf_counter() - case_start
                    fail_count += 1
                    print(
                        (
                            f"[{job_index}/{total_jobs}] FAIL artist={artist_key} series={series_key} "
                            f"run={n} after {elapsed:.2f}s: {exc}"
                        ),
                        flush=True,
                    )
                    continue

    total_elapsed = time.perf_counter() - overall_start
    print("=== Benchmark v2 Summary ===", flush=True)
    print(f"Success: {success_count}", flush=True)
    print(f"Failed: {fail_count}", flush=True)
    print(f"Total elapsed: {total_elapsed:.2f}s", flush=True)


if __name__ == "__main__":
    main()
