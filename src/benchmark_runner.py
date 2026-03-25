#!/usr/bin/env python3
"""ComfyUI API 기반 벤치마크 러너.

- HTTP 폴링 방식으로 /prompt 제출 후 /history 결과 확인
- 3개 모델 x 5개 프롬프트 x 2회 = 총 30장 생성
- 생성 완료 이미지를 로컬(data/benchmark)로 다운로드 저장
"""

from __future__ import annotations

import random
import statistics
import time
import uuid
from pathlib import Path
from typing import Any

import requests

# ComfyUI 서버 설정
COMFY_BASE_URL = "http://127.0.0.1:8188"

# 출력 경로 설정
OUTPUT_DIR = Path("/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/data/benchmark")

# 이미지 크기
WIDTH = 832
HEIGHT = 1216

# SDXL 공통 네거티브 프롬프트
SDXL_NEGATIVE_PROMPT = (
    "lowres, bad anatomy, bad hands, text, error, worst quality, low quality, "
    "child, loli, flat_chest, school_uniform, nude, nipples, genitals"
)

# 프롬프트 세트 (Illustrious/WAI 기준)
PROMPTS_SD = {
    "A": "masterpiece, best quality, 1girl, solo, mature_female, voluptuous, black latex_suit, full_body, skin_tight, shiny, glossy, standing, looking_at_viewer, laboratory, white_tiles, fluorescent_light, gas_mask, black_gloves",
    "B": "masterpiece, best quality, 1girl, solo, mature_female, voluptuous, black latex_suit, catsuit, skin_tight, shiny, glossy, collar, leash, kneeling, arms_behind_back, dungeon, concrete_wall, dim_lighting, chains, latex_mask, full_face_mask, faceless",
    "C": "masterpiece, best quality, 1girl, solo, mature_female, voluptuous, black_and_orange latex_suit, skin_tight, shiny, glossy, cyberpunk, neon_lights, rain, wet, night_city, gas_mask, standing, hand_on_hip, reflection, puddle, neon_sign",
    "D": "masterpiece, best quality, 1girl, solo, mature_female, voluptuous, black latex_suit, skin_tight, shiny, glossy, ball_gag, blindfold, collar, bound_wrists, latex_gloves, thigh_highs, high_heels, dungeon, spotlight, dark_background",
    "E": "masterpiece, best quality, 1girl, solo, mature_female, voluptuous, black leotard, thigh_highs, high_heels, shiny, glossy, skin_tight, mask, half_mask, mysterious, bedroom, mood_lighting, curtains, sitting, crossed_legs, elegant_pose",
}

# Pony 프롬프트 접두사
PONY_PREFIX = "score_9, score_8_up, score_7_up, source_anime, rating_explicit, "

# Flux 자연어 프롬프트
PROMPTS_FLUX = {
    "A": "A voluptuous mature woman in a skin-tight glossy black latex full-body suit, wearing a black gas mask covering her entire face. She stands in a sterile white-tiled laboratory under fluorescent lights. The latex suit has an extremely shiny, reflective surface. Black latex gloves. Anime art style, high detail, dramatic lighting.",
    "B": "A voluptuous mature woman wearing a glossy black latex catsuit that covers her entire body, with a full-face latex mask making her faceless. She kneels with arms behind her back in a dark concrete dungeon. A leather collar with a leash around her neck. Chains hang from the walls. Dim dramatic lighting. Anime art style.",
    "C": "A voluptuous mature woman in a skin-tight black and orange latex suit with extremely glossy reflective surface. She wears a gas mask covering her face. Standing confidently in a rainy cyberpunk night city street, neon signs reflecting in wet puddles. Rain droplets on the shiny latex. Anime art style, vibrant neon colors.",
    "D": "A voluptuous mature woman in a skin-tight glossy black latex bodysuit with long black latex gloves and black thigh-high latex stockings with high heels. She wears a ball gag in her mouth and a blindfold over her eyes, with a leather collar around her neck and wrists bound. In a dark dungeon illuminated by a single spotlight. Anime art style.",
    "E": "A voluptuous mature woman wearing a glossy black leotard with black thigh-high stockings and high heels. She wears a mysterious half-mask covering the upper half of her face. Sitting elegantly with crossed legs in a dimly lit bedroom with flowing curtains. The leotard has a shiny, latex-like material. Anime art style, elegant mood.",
}

# 벤치마크 모델 설정
MODELS = {
    "wai": {
        "checkpoint": "waiIllustriousSDXL_v160.safetensors",
        "steps": 25,
        "cfg": 7,
        "vae": "sdxl_vae.safetensors",
        "loras": [
            ("latex_huger_c7-1+76-1+64-4.safetensors", 0.7),
            ("Shiny_Clothes_and_Skin_Latex_Illustrious.safetensors", 0.5),
        ],
        "prompt_mode": "sd",
    },
    "pony": {
        "checkpoint": "ponyDiffusionV6XL_v6StartWithThisOne.safetensors",
        "steps": 25,
        "cfg": 7,
        "vae": "sdxl_vae.safetensors",
        "loras": [
            ("latex_huger_c7-1+76-1+64-4.safetensors", 0.7),
            ("Shiny_Clothes_and_Skin_Latex_Illustrious.safetensors", 0.5),
        ],
        "prompt_mode": "pony",
    },
    "flux": {
        "checkpoint": "flux1-schnell-fp8.safetensors",
        "steps": 4,
        "cfg": 1,
        "vae": "ae.safetensors",
        "loras": [],
        "prompt_mode": "flux",
    },
}


def build_sdxl_workflow(
    checkpoint_name: str,
    vae_name: str,
    loras: list[tuple[str, float]],
    positive_prompt: str,
    negative_prompt: str,
    steps: int,
    cfg: float,
    seed: int,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    """SDXL 계열용 ComfyUI 워크플로우 생성."""

    # 기본 노드 구성
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": positive_prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["6", 0]},
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": filename_prefix, "images": ["7", 0]},
        },
    }

    # LoRA 체인 구성 (Checkpoint model/clip -> LoraLoader -> 다음 LoraLoader ...)
    model_source: list[Any] = ["1", 0]
    clip_source: list[Any] = ["1", 1]
    next_node_id = 20

    for lora_name, strength in loras:
        node_id = str(next_node_id)
        workflow[node_id] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_name,
                "strength_model": strength,
                "strength_clip": strength,
                "model": model_source,
                "clip": clip_source,
            },
        }
        model_source = [node_id, 0]
        clip_source = [node_id, 1]
        next_node_id += 1

    # LoRA가 있을 경우 KSampler/CLIP 인풋 교체
    if loras:
        workflow["2"]["inputs"]["clip"] = clip_source
        workflow["3"]["inputs"]["clip"] = clip_source
        workflow["5"]["inputs"]["model"] = model_source

    return workflow, "8"


def build_flux_workflow(
    checkpoint_name: str,
    vae_name: str,
    prompt: str,
    steps: int,
    guidance: float,
    seed: int,
    filename_prefix: str,
) -> tuple[dict[str, Any], str]:
    """Flux용 ComfyUI 워크플로우 생성 (ModelSamplingFlux + BasicScheduler + SamplerCustomAdvanced)."""

    workflow: dict[str, Any] = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint_name},
        },
        "2": {
            "class_type": "ModelSamplingFlux",
            "inputs": {
                "model": ["1", 0],
                "max_shift": 1.15,
                "base_shift": 0.50,
                "width": WIDTH,
                "height": HEIGHT,
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "FluxGuidance",
            "inputs": {"conditioning": ["3", 0], "guidance": guidance},
        },
        "5": {
            "class_type": "BasicGuider",
            "inputs": {"model": ["2", 0], "conditioning": ["4", 0]},
        },
        "6": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["2", 0],
                "scheduler": "simple",
                "steps": steps,
                "denoise": 1.0,
            },
        },
        "7": {
            "class_type": "KSamplerSelect",
            "inputs": {"sampler_name": "euler"},
        },
        "8": {
            "class_type": "RandomNoise",
            "inputs": {"noise_seed": seed},
        },
        "9": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": WIDTH, "height": HEIGHT, "batch_size": 1},
        },
        "10": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["8", 0],
                "guider": ["5", 0],
                "sampler": ["7", 0],
                "sigmas": ["6", 0],
                "latent_image": ["9", 0],
            },
        },
        "11": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "12": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["10", 0], "vae": ["11", 0]},
        },
        "13": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": filename_prefix, "images": ["12", 0]},
        },
    }

    return workflow, "13"


def submit_prompt(session: requests.Session, workflow: dict[str, Any]) -> str:
    """/prompt로 워크플로우를 제출하고 prompt_id를 반환."""

    payload = {
        "prompt": workflow,
        "client_id": f"benchmark_runner_{uuid.uuid4()}",
    }
    response = session.post(f"{COMFY_BASE_URL}/prompt", json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    prompt_id = data.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"/prompt 응답에 prompt_id가 없습니다: {data}")
    return prompt_id


def fetch_history_entry(session: requests.Session, prompt_id: str) -> dict[str, Any] | None:
    """/history에서 특정 prompt_id 실행 결과를 조회."""

    # 1) /history/{prompt_id} 시도
    response = session.get(f"{COMFY_BASE_URL}/history/{prompt_id}", timeout=30)
    if response.status_code == 200:
        data = response.json()
        if isinstance(data, dict):
            if prompt_id in data:
                return data[prompt_id]
            if data:
                # 서버/버전에 따라 단일 엔트리 구조가 달라질 수 있어 첫 값 fallback
                return next(iter(data.values()))

    # 2) /history 전체에서 탐색 fallback
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
    """history를 폴링하여 결과 이미지 메타데이터 리스트를 반환."""

    start = time.perf_counter()

    while True:
        if time.perf_counter() - start > timeout_sec:
            raise TimeoutError(f"생성 타임아웃: prompt_id={prompt_id}")

        entry = fetch_history_entry(session, prompt_id)
        if entry:
            status = entry.get("status", {})
            # 실행 중 에러 체크
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
    """/view 엔드포인트로 이미지를 받아 로컬 파일로 저장."""

    params = {
        "filename": image_info.get("filename", ""),
        "subfolder": image_info.get("subfolder", ""),
        "type": image_info.get("type", "output"),
    }
    response = session.get(f"{COMFY_BASE_URL}/view", params=params, timeout=60)
    response.raise_for_status()
    output_path.write_bytes(response.content)


def get_prompt(model_key: str, prompt_key: str) -> str:
    """모델 타입에 맞는 프롬프트를 반환."""

    mode = MODELS[model_key]["prompt_mode"]
    if mode == "sd":
        return PROMPTS_SD[prompt_key]
    if mode == "pony":
        return PONY_PREFIX + PROMPTS_SD[prompt_key]
    if mode == "flux":
        return PROMPTS_FLUX[prompt_key]
    raise ValueError(f"알 수 없는 prompt_mode: {mode}")


def main() -> None:
    """벤치마크 전체 실행."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    # 서버 연결 확인
    try:
        health = session.get(f"{COMFY_BASE_URL}/system_stats", timeout=10)
        health.raise_for_status()
    except requests.RequestException as exc:
        raise SystemExit(f"ComfyUI 연결 실패 ({COMFY_BASE_URL}): {exc}") from exc

    print("=== ComfyUI Benchmark Runner 시작 ===")
    print(f"서버: {COMFY_BASE_URL}")
    print(f"저장 경로: {OUTPUT_DIR}")
    print("총 작업 수: 30 (3 모델 x 5 프롬프트 x 2회)")

    timings_by_model: dict[str, list[float]] = {"wai": [], "pony": [], "flux": []}
    total_start = time.perf_counter()

    for model_key, model_cfg in MODELS.items():
        for prompt_key in ["A", "B", "C", "D", "E"]:
            for n in [1, 2]:
                filename = f"benchmark_{model_key}_{prompt_key}_{n}.png"
                out_file = OUTPUT_DIR / filename
                prompt_text = get_prompt(model_key, prompt_key)
                seed = random.randint(0, 2**31 - 1)

                if model_key in ("wai", "pony"):
                    workflow, save_node_id = build_sdxl_workflow(
                        checkpoint_name=model_cfg["checkpoint"],
                        vae_name=model_cfg["vae"],
                        loras=model_cfg["loras"],
                        positive_prompt=prompt_text,
                        negative_prompt=SDXL_NEGATIVE_PROMPT,
                        steps=model_cfg["steps"],
                        cfg=model_cfg["cfg"],
                        seed=seed,
                        filename_prefix=filename.replace(".png", ""),
                    )
                else:
                    workflow, save_node_id = build_flux_workflow(
                        checkpoint_name=model_cfg["checkpoint"],
                        vae_name=model_cfg["vae"],
                        prompt=prompt_text,
                        steps=model_cfg["steps"],
                        guidance=model_cfg["cfg"],
                        seed=seed,
                        filename_prefix=filename.replace(".png", ""),
                    )

                print(f"\n[{model_key.upper()}][{prompt_key}][{n}/2] 생성 시작: {filename}")
                case_start = time.perf_counter()

                prompt_id = submit_prompt(session, workflow)
                images = wait_for_completion(session, prompt_id, save_node_id)
                download_image(session, images[0], out_file)

                elapsed = time.perf_counter() - case_start
                timings_by_model[model_key].append(elapsed)
                print(f"완료: {out_file} ({elapsed:.2f}s)")

    total_elapsed = time.perf_counter() - total_start

    print("\n=== 벤치마크 요약 ===")
    for model_key in ["wai", "pony", "flux"]:
        times = timings_by_model[model_key]
        avg = statistics.mean(times) if times else 0.0
        print(f"- {model_key}: {len(times)}장, 평균 {avg:.2f}s")

    print(f"전체 소요 시간: {total_elapsed:.2f}s")


if __name__ == "__main__":
    main()
