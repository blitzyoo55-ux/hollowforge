"""Application configuration with environment variable overrides."""

from __future__ import annotations

import os
from pathlib import Path


# Resolve paths relative to the backend directory
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_HOLLOWFORGE_DIR = _BACKEND_DIR.parent


def _parse_path_list(raw: str | None) -> tuple[Path, ...]:
    if not raw:
        return ()
    return tuple(Path(p.strip()).expanduser() for p in raw.split(",") if p.strip())


class Settings:
    """Central configuration. Reads from env vars with sensible defaults."""

    COMFYUI_URL: str = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")

    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(_HOLLOWFORGE_DIR / "data")))
    DB_PATH: Path = DATA_DIR / "hollowforge.db"
    IMAGES_DIR: Path = DATA_DIR / "images"
    THUMBS_DIR: Path = DATA_DIR / "thumbs"
    WORKFLOWS_DIR: Path = DATA_DIR / "workflows"
    PINOKIO_PEERS_DIR: Path = Path(
        os.getenv(
            "PINOKIO_PEERS_DIR",
            str(Path.home() / "AI_Projects/pinokio/drive/drives/peers"),
        )
    )
    UPSCALE_MODELS_DIRS: tuple[Path, ...] = _parse_path_list(
        os.getenv("UPSCALE_MODELS_DIRS")
    ) or (
        _HOLLOWFORGE_DIR / "models" / "upscale_models",
        Path.home() / "ComfyUI" / "models" / "upscale_models",
    )

    DEFAULT_CHECKPOINT: str = os.getenv(
        "DEFAULT_CHECKPOINT", "waiIllustriousSDXL_v160.safetensors"
    )
    MAX_CONCURRENT_GENERATIONS: int = int(
        os.getenv("MAX_CONCURRENT_GENERATIONS", "1")
    )
    POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "1.0"))
    GENERATION_TIMEOUT: int = int(os.getenv("GENERATION_TIMEOUT", "900"))


settings = Settings()
