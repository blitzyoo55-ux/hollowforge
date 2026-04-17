"""Application configuration with environment variable overrides."""

from __future__ import annotations

import os
from pathlib import Path


# Resolve paths relative to the backend directory
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_HOLLOWFORGE_DIR = _BACKEND_DIR.parent
_WORKSPACE_ROOT = _HOLLOWFORGE_DIR.parents[2]


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE pairs from backend/.env without extra dependencies."""
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
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


_load_env_file(_BACKEND_DIR / ".env")


def _parse_path_list(raw: str | None) -> tuple[Path, ...]:
    if not raw:
        return ()
    return tuple(Path(p.strip()).expanduser() for p in raw.split(",") if p.strip())


def _env_path(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _unique_paths(paths: list[Path]) -> tuple[Path, ...]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return tuple(unique)


def _first_existing_dir(paths: tuple[Path, ...]) -> Path | None:
    for path in paths:
        if path.is_dir():
            return path
    return None


def _pinokio_root_candidates() -> tuple[Path, ...]:
    return _unique_paths(
        [
            _WORKSPACE_ROOT / "pinokio",
            Path.home() / "AI_Projects" / "pinokio",
            Path.home() / "AI_projects" / "pinokio",
        ]
    )


def _resolve_pinokio_root_dir() -> Path:
    explicit = _env_path("PINOKIO_ROOT_DIR")
    if explicit is not None:
        return explicit
    return _first_existing_dir(_pinokio_root_candidates()) or (_WORKSPACE_ROOT / "pinokio")


def _resolve_pinokio_peers_dir(pinokio_root_dir: Path) -> Path:
    explicit = _env_path("PINOKIO_PEERS_DIR")
    if explicit is not None:
        return explicit
    candidates = _unique_paths(
        [pinokio_root_dir / "drive" / "drives" / "peers"]
        + [root / "drive" / "drives" / "peers" for root in _pinokio_root_candidates()]
    )
    return _first_existing_dir(candidates) or (pinokio_root_dir / "drive" / "drives" / "peers")


def _resolve_pinokio_primary_peer_dir(peers_dir: Path) -> Path | None:
    peer_id = os.getenv("PINOKIO_PEER_ID", "").strip()
    if peer_id:
        return peers_dir / peer_id
    if not peers_dir.is_dir():
        return None
    peer_dirs = sorted((p for p in peers_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    return peer_dirs[0] if peer_dirs else None


def _resolve_pinokio_output_dir(primary_peer_dir: Path | None) -> Path | None:
    explicit = _env_path("PINOKIO_OUTPUT_DIR")
    if explicit is not None:
        return explicit
    if primary_peer_dir is None:
        return None
    return primary_peer_dir / "output"


def _resolve_pinokio_comfy_models_dir(pinokio_root_dir: Path) -> Path:
    explicit_models_dir = _env_path("PINOKIO_COMFY_MODELS_DIR")
    if explicit_models_dir is not None:
        return explicit_models_dir
    explicit_app_dir = _env_path("PINOKIO_COMFY_APP_DIR")
    if explicit_app_dir is not None:
        return explicit_app_dir / "models"
    candidates = _unique_paths(
        [pinokio_root_dir / "api" / "comfy.git" / "app" / "models"]
        + [root / "api" / "comfy.git" / "app" / "models" for root in _pinokio_root_candidates()]
    )
    return _first_existing_dir(candidates) or (pinokio_root_dir / "api" / "comfy.git" / "app" / "models")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Central configuration. Reads from env vars with sensible defaults."""

    COMFYUI_URL: str = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
    DEFAULT_NEGATIVE_PROMPT: str = os.getenv(
        "HOLLOWFORGE_DEFAULT_NEGATIVE_PROMPT",
        (
            "child, teen, underage, school uniform, "
            "text, logo, watermark, blurry, lowres, "
            "deformed, cropped face"
        ),
    ).strip() or (
        "child, teen, underage, school uniform, "
        "text, logo, watermark, blurry, lowres, "
        "deformed, cropped face"
    )
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", "")
    XAI_API_BASE_URL: str = os.getenv("XAI_API_BASE_URL", "https://api.x.ai/v1").strip()
    MARKETING_MODEL: str = os.getenv("MARKETING_MODEL", "x-ai/grok-2-vision-1212")
    MARKETING_PROVIDER_NAME: str = os.getenv("MARKETING_PROVIDER_NAME", "openrouter")
    MARKETING_PROMPT_VERSION: str = os.getenv(
        "MARKETING_PROMPT_VERSION",
        "lab451_social_v1",
    )
    PROMPT_FACTORY_PROVIDER: str = os.getenv(
        "PROMPT_FACTORY_PROVIDER",
        "openrouter",
    ).strip().lower() or "openrouter"
    PROMPT_FACTORY_OPENROUTER_MODEL: str = os.getenv(
        "PROMPT_FACTORY_OPENROUTER_MODEL",
        "x-ai/grok-4.1-fast",
    ).strip() or "x-ai/grok-4.1-fast"
    PROMPT_FACTORY_XAI_MODEL: str = os.getenv(
        "PROMPT_FACTORY_XAI_MODEL",
        "grok-4-1-fast-non-reasoning",
    ).strip() or "grok-4-1-fast-non-reasoning"
    PROMPT_FACTORY_CHUNK_SIZE: int = int(
        os.getenv("PROMPT_FACTORY_CHUNK_SIZE", "20")
    )
    PROMPT_FACTORY_TEMPERATURE: float = float(
        os.getenv("PROMPT_FACTORY_TEMPERATURE", "0.9")
    )
    PUBLISH_DEFAULT_ANIMATION_TOOL: str = os.getenv(
        "HOLLOWFORGE_PUBLISH_DEFAULT_ANIMATION_TOOL",
        "dreamactor",
    ).strip().lower() or "dreamactor"
    HOLLOWFORGE_SEQUENCE_FFMPEG_BIN: str = os.getenv(
        "HOLLOWFORGE_SEQUENCE_FFMPEG_BIN",
        "ffmpeg",
    ).strip() or "ffmpeg"
    HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE: str = os.getenv(
        "HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE",
        "safe_hosted_grok",
    ).strip() or "safe_hosted_grok"
    HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE: str = os.getenv(
        "HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE",
        "adult_local_llm",
    ).strip() or "adult_local_llm"
    HOLLOWFORGE_SEQUENCE_LOCAL_LLM_BASE_URL: str = os.getenv(
        "HOLLOWFORGE_SEQUENCE_LOCAL_LLM_BASE_URL",
        "http://127.0.0.1:11434/v1",
    ).strip() or "http://127.0.0.1:11434/v1"
    HOLLOWFORGE_SEQUENCE_LOCAL_LLM_MODEL: str = os.getenv(
        "HOLLOWFORGE_SEQUENCE_LOCAL_LLM_MODEL",
        "llama3.1",
    ).strip() or "llama3.1"
    PUBLISH_ANIMATION_SCORE_THRESHOLD: float = float(
        os.getenv("HOLLOWFORGE_PUBLISH_ANIMATION_SCORE_THRESHOLD", "30")
    )
    PUBLISH_ANIMATION_BOOKMARK_THRESHOLD: int = int(
        os.getenv("HOLLOWFORGE_PUBLISH_ANIMATION_BOOKMARK_THRESHOLD", "8")
    )
    ANIMATION_EXECUTOR_MODE: str = os.getenv(
        "HOLLOWFORGE_ANIMATION_EXECUTOR_MODE",
        "remote_worker",
    ).strip().lower() or "remote_worker"
    ANIMATION_EXECUTOR_KEY: str = os.getenv(
        "HOLLOWFORGE_ANIMATION_EXECUTOR_KEY",
        "default",
    ).strip() or "default"
    ANIMATION_REMOTE_BASE_URL: str = os.getenv(
        "HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL",
        "",
    ).strip()
    PUBLIC_API_BASE_URL: str = os.getenv(
        "HOLLOWFORGE_PUBLIC_API_BASE_URL",
        "http://127.0.0.1:8000",
    ).strip()
    ANIMATION_WORKER_API_TOKEN: str = os.getenv(
        "HOLLOWFORGE_ANIMATION_WORKER_API_TOKEN",
        "",
    ).strip()
    ANIMATION_CALLBACK_TOKEN: str = os.getenv(
        "HOLLOWFORGE_ANIMATION_CALLBACK_TOKEN",
        "",
    ).strip()
    HOLLOWFORGE_REFERENCE_GUIDED_IPADAPTER_WEIGHT: float = float(
        os.getenv("HOLLOWFORGE_REFERENCE_GUIDED_IPADAPTER_WEIGHT", "0.92")
    )
    HOLLOWFORGE_REFERENCE_GUIDED_IPADAPTER_START_AT: float = float(
        os.getenv("HOLLOWFORGE_REFERENCE_GUIDED_IPADAPTER_START_AT", "0.0")
    )
    HOLLOWFORGE_REFERENCE_GUIDED_IPADAPTER_END_AT: float = float(
        os.getenv("HOLLOWFORGE_REFERENCE_GUIDED_IPADAPTER_END_AT", "1.0")
    )
    HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_ADAPTER_PROFILE: str = os.getenv(
        "HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_ADAPTER_PROFILE",
        "plus_face",
    ).strip()
    HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_ENABLED: bool = _env_flag(
        "HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_ENABLED",
        True,
    )
    HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_DENOISE: float = float(
        os.getenv("HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_DENOISE", "0.28")
    )
    HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_STRENGTH: float = float(
        os.getenv("HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_STRENGTH", "0.82")
    )
    HOLLOWFORGE_REFERENCE_GUIDED_ESTABLISH_INCLUDE_SECONDARY: bool = _env_flag(
        "HOLLOWFORGE_REFERENCE_GUIDED_ESTABLISH_INCLUDE_SECONDARY",
        True,
    )
    ANIMATION_REMOTE_SUBMIT_TIMEOUT_SEC: float = float(
        os.getenv("HOLLOWFORGE_ANIMATION_REMOTE_SUBMIT_TIMEOUT_SEC", "20")
    )
    ANIMATION_MANAGED_PROVIDER: str = os.getenv(
        "HOLLOWFORGE_ANIMATION_MANAGED_PROVIDER",
        "byteplus",
    ).strip().lower() or "byteplus"
    LEAN_MODE: bool = _env_flag("HOLLOWFORGE_LEAN_MODE", default=False)
    AUTO_UPSCALE_FAVORITES: bool = _env_flag(
        "HOLLOWFORGE_AUTO_UPSCALE_FAVORITES",
        default=False,
    )
    UPSCALE_USE_ULTIMATE: bool = _env_flag(
        "HOLLOWFORGE_UPSCALE_USE_ULTIMATE",
        default=False,
    )
    UPSCALE_QUALITY_ENABLED: bool = _env_flag(
        "HOLLOWFORGE_UPSCALE_QUALITY_ENABLED",
        default=False,
    )
    UPSCALE_SAFE_USE_COMFYUI: bool = _env_flag(
        "HOLLOWFORGE_UPSCALE_SAFE_USE_COMFYUI",
        default=False,
    )
    FAVORITE_UPSCALE_DAILY_ENABLED: bool = _env_flag(
        "HOLLOWFORGE_FAVORITE_UPSCALE_DAILY_ENABLED",
        default=False,
    )
    FAVORITE_UPSCALE_DAILY_HOUR: int = int(
        os.getenv("HOLLOWFORGE_FAVORITE_UPSCALE_DAILY_HOUR", "4")
    )
    FAVORITE_UPSCALE_DAILY_MINUTE: int = int(
        os.getenv("HOLLOWFORGE_FAVORITE_UPSCALE_DAILY_MINUTE", "0")
    )
    FAVORITE_UPSCALE_DAILY_BATCH_LIMIT: int = int(
        os.getenv("HOLLOWFORGE_FAVORITE_UPSCALE_DAILY_BATCH_LIMIT", "5")
    )
    FAVORITE_UPSCALE_MODE: str = os.getenv(
        "HOLLOWFORGE_FAVORITE_UPSCALE_MODE",
        "safe",
    ).strip().lower() or "safe"
    FAVORITE_UPSCALE_BACKLOG_START_HOUR: int = int(
        os.getenv("HOLLOWFORGE_FAVORITE_UPSCALE_BACKLOG_START_HOUR", "1")
    )
    FAVORITE_UPSCALE_BACKLOG_END_HOUR: int = int(
        os.getenv("HOLLOWFORGE_FAVORITE_UPSCALE_BACKLOG_END_HOUR", "8")
    )

    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(_HOLLOWFORGE_DIR / "data")))
    DB_PATH: Path = DATA_DIR / "hollowforge.db"
    IMAGES_DIR: Path = DATA_DIR / "images"
    THUMBS_DIR: Path = DATA_DIR / "thumbs"
    WORKFLOWS_DIR: Path = DATA_DIR / "workflows"
    COMICS_DIR: Path = DATA_DIR / "comics"
    COMICS_PREVIEWS_DIR: Path = COMICS_DIR / "previews"
    COMICS_EXPORTS_DIR: Path = COMICS_DIR / "exports"
    COMICS_MANIFESTS_DIR: Path = COMICS_DIR / "manifests"
    PINOKIO_ROOT_DIR: Path = _resolve_pinokio_root_dir()
    PINOKIO_PEERS_DIR: Path = _resolve_pinokio_peers_dir(PINOKIO_ROOT_DIR)
    PINOKIO_PRIMARY_PEER_DIR: Path | None = _resolve_pinokio_primary_peer_dir(
        PINOKIO_PEERS_DIR
    )
    PINOKIO_OUTPUT_DIR: Path | None = _resolve_pinokio_output_dir(
        PINOKIO_PRIMARY_PEER_DIR
    )
    PINOKIO_COMFY_MODELS_DIR: Path = _resolve_pinokio_comfy_models_dir(
        PINOKIO_ROOT_DIR
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
    COMFYUI_METADATA_CACHE_TTL_SEC: float = float(
        os.getenv("COMFYUI_METADATA_CACHE_TTL_SEC", "15")
    )
    MODEL_COMPATIBILITY_CACHE_TTL_SEC: float = float(
        os.getenv("MODEL_COMPATIBILITY_CACHE_TTL_SEC", "30")
    )
    MAX_CONCURRENT_GENERATIONS: int = int(
        os.getenv("MAX_CONCURRENT_GENERATIONS", "1")
    )
    POLL_INTERVAL: float = float(os.getenv("POLL_INTERVAL", "1.0"))
    GENERATION_TIMEOUT: int = int(os.getenv("GENERATION_TIMEOUT", "900"))

    @property
    def COMICS_REPORTS_DIR(self) -> Path:
        path = self.COMICS_DIR / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()

for _directory in (
    settings.DATA_DIR,
    settings.COMICS_DIR,
    settings.COMICS_PREVIEWS_DIR,
    settings.COMICS_EXPORTS_DIR,
    settings.COMICS_MANIFESTS_DIR,
    settings.COMICS_REPORTS_DIR,
):
    _directory.mkdir(parents=True, exist_ok=True)
