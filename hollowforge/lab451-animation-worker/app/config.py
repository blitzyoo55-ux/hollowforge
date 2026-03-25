"""Configuration for the Lab451 animation worker."""

from __future__ import annotations

import os
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent
_WORKER_DIR = _APP_DIR.parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        os.environ.setdefault(key, value.strip().strip("'").strip('"'))


_load_env_file(_WORKER_DIR / ".env")


class Settings:
    WORKER_API_TOKEN: str = os.getenv("WORKER_API_TOKEN", "").strip()
    WORKER_EXECUTOR_BACKEND: str = os.getenv(
        "WORKER_EXECUTOR_BACKEND",
        "stub",
    ).strip().lower() or "stub"
    WORKER_PUBLIC_BASE_URL: str = os.getenv(
        "WORKER_PUBLIC_BASE_URL",
        "http://127.0.0.1:8600",
    ).strip()
    WORKER_CALLBACK_TIMEOUT_SEC: float = float(
        os.getenv("WORKER_CALLBACK_TIMEOUT_SEC", "20")
    )
    WORKER_STUB_SUBMIT_DELAY_SEC: float = float(
        os.getenv("WORKER_STUB_SUBMIT_DELAY_SEC", "0.2")
    )
    WORKER_STUB_PROCESS_DELAY_SEC: float = float(
        os.getenv("WORKER_STUB_PROCESS_DELAY_SEC", "0.4")
    )
    WORKER_DEFAULT_NEGATIVE_PROMPT: str = os.getenv(
        "WORKER_DEFAULT_NEGATIVE_PROMPT",
        "child, teen, underage, school uniform, text, logo, watermark, blurry, lowres, deformed, cropped face",
    ).strip()
    WORKER_COMFYUI_URL: str = os.getenv(
        "WORKER_COMFYUI_URL",
        "http://127.0.0.1:8188",
    ).strip()
    WORKER_COMFYUI_POLL_INTERVAL_SEC: float = float(
        os.getenv("WORKER_COMFYUI_POLL_INTERVAL_SEC", "2.0")
    )
    WORKER_COMFYUI_TIMEOUT_SEC: float = float(
        os.getenv("WORKER_COMFYUI_TIMEOUT_SEC", "1800")
    )
    WORKER_COMFYUI_LTXV_CHECKPOINT: str = os.getenv(
        "WORKER_COMFYUI_LTXV_CHECKPOINT",
        "ltxv-2b-0.9.8-distilled-fp8.safetensors",
    ).strip()
    WORKER_COMFYUI_LTXV_CHECKPOINT_FALLBACK: str = os.getenv(
        "WORKER_COMFYUI_LTXV_CHECKPOINT_FALLBACK",
        "ltx-video-2b-v0.9.5.safetensors",
    ).strip()
    WORKER_COMFYUI_LTXV_TEXT_ENCODER: str = os.getenv(
        "WORKER_COMFYUI_LTXV_TEXT_ENCODER",
        "t5xxl_fp16.safetensors",
    ).strip()
    WORKER_COMFYUI_IPADAPTER_MODEL: str = os.getenv(
        "WORKER_COMFYUI_IPADAPTER_MODEL",
        "ipAdapterPlusSd15_ipAdapterPlusSdxlVit.safetensors",
    ).strip()
    WORKER_COMFYUI_CLIP_VISION_MODEL: str = os.getenv(
        "WORKER_COMFYUI_CLIP_VISION_MODEL",
        "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    ).strip()
    WORKER_COMFYUI_IMAGE_COMPRESSION: int = int(
        os.getenv("WORKER_COMFYUI_IMAGE_COMPRESSION", "35")
    )
    DATA_DIR: Path = Path(os.getenv("WORKER_DATA_DIR", str(_WORKER_DIR / "data")))
    DB_PATH: Path = DATA_DIR / "animation_worker.db"
    OUTPUTS_DIR: Path = DATA_DIR / "outputs"
    INPUTS_DIR: Path = DATA_DIR / "inputs"


settings = Settings()
