"""Preflight checks for the local HollowForge animation stack."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = ROOT_DIR.parents[2]


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


def _env_path(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _first_existing_dir(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.is_dir():
            return path
    return None


def _candidate_pinokio_roots() -> list[Path]:
    return _unique_paths(
        [
            WORKSPACE_ROOT / "pinokio",
            Path.home() / "AI_Projects" / "pinokio",
            Path.home() / "AI_projects" / "pinokio",
        ]
    )


def _resolve_comfy_models_dir() -> Path:
    explicit_models_dir = _env_path("PINOKIO_COMFY_MODELS_DIR")
    if explicit_models_dir is not None:
        return explicit_models_dir
    explicit_app_dir = _env_path("PINOKIO_COMFY_APP_DIR")
    if explicit_app_dir is not None:
        return explicit_app_dir / "models"
    explicit_root_dir = _env_path("PINOKIO_ROOT_DIR")
    if explicit_root_dir is not None:
        return explicit_root_dir / "api" / "comfy.git" / "app" / "models"
    candidates = _unique_paths(
        [root / "api" / "comfy.git" / "app" / "models" for root in _candidate_pinokio_roots()]
    )
    return _first_existing_dir(candidates) or (
        WORKSPACE_ROOT / "pinokio" / "api" / "comfy.git" / "app" / "models"
    )


_load_env_file(ROOT_DIR / "backend" / ".env")
COMFY_MODELS_DIR = _resolve_comfy_models_dir()
COMFY_URL = "http://127.0.0.1:8188"
BACKEND_URL = "http://127.0.0.1:8000"
WORKER_URL = "http://127.0.0.1:8600"
REQUIRED_NODES = [
    "LTXVImgToVideo",
    "LTXVConditioning",
    "LTXVScheduler",
    "ModelSamplingLTXV",
    "CreateVideo",
    "SaveVideo",
]
REQUIRED_IPADAPTER_NODES = [
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
]
REQUIRED_CHECKPOINTS = [
    "ltx-2.3-22b-distilled.safetensors",
    "ltxv-2b-0.9.8-distilled-fp8.safetensors",
    "ltx-video-2b-v0.9.5.safetensors",
]
REQUIRED_TEXT_ENCODERS = [
    "t5xxl_fp16.safetensors",
]
REQUIRED_IPADAPTER_MODELS = [
    "ipAdapterPlusSd15_ipAdapterPlusSdxlVit.safetensors",
]
REQUIRED_PLUS_FACE_IPADAPTER_MODELS = [
    "ip-adapter-plus-face_sdxl_vit-h.safetensors",
]
OPTIONAL_FACEID_IPADAPTER_MODELS = [
    "ip-adapter-faceid-plusv2_sdxl.bin",
]
OPTIONAL_FACEID_LORA_MODELS = [
    "ip-adapter-faceid-plusv2_sdxl_lora.safetensors",
]
REQUIRED_CLIP_VISION_MODELS = [
    "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
]
OPTIONAL_NOOBAI_CHECKPOINT_MODELS = [
    "noobaiXLNAIXL_vPred10Version.safetensors",
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _fetch_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return data


def _api_check(name: str, url: str, success_detail: str) -> CheckResult:
    try:
        _fetch_json(url)
        return CheckResult(name=name, ok=True, detail=success_detail)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return CheckResult(name=name, ok=False, detail=str(exc))


def _file_exists(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _model_paths(name: str) -> list[Path]:
    return [
        COMFY_MODELS_DIR / "checkpoints" / name,
        COMFY_MODELS_DIR / "diffusion_models" / name,
        COMFY_MODELS_DIR / "unet" / name,
    ]


def _text_encoder_paths(name: str) -> list[Path]:
    return [
        COMFY_MODELS_DIR / "clip" / name,
        COMFY_MODELS_DIR / "text_encoders" / name,
    ]


def _ipadapter_paths(name: str) -> list[Path]:
    return [
        COMFY_MODELS_DIR / "ipadapter" / name,
    ]


def _clip_vision_paths(name: str) -> list[Path]:
    return [
        COMFY_MODELS_DIR / "clip_vision" / name,
    ]


def _checkpoint_only_paths(name: str) -> list[Path]:
    return [
        COMFY_MODELS_DIR / "checkpoints" / name,
    ]


def _loras_paths(name: str) -> list[Path]:
    return [
        COMFY_MODELS_DIR / "loras" / name,
    ]


def _check_asset(
    name: str,
    paths: list[Path],
    *,
    result_name: str,
    required: bool,
    missing_detail: str,
) -> CheckResult:
    path = _file_exists(paths)
    if path is not None:
        return CheckResult(
            name=result_name,
            ok=True,
            detail=f"found {name} at {path}",
        )
    return CheckResult(
        name=result_name,
        ok=False,
        detail=f"{missing_detail}: {name}",
        required=required,
    )


def _check_required_checkpoint() -> CheckResult:
    for name in REQUIRED_CHECKPOINTS:
        path = _file_exists(_model_paths(name))
        if path is not None:
            return CheckResult(
                name="ltxv_checkpoint",
                ok=True,
                detail=f"found {name} at {path}",
            )
    expected = ", ".join(REQUIRED_CHECKPOINTS)
    return CheckResult(
        name="ltxv_checkpoint",
        ok=False,
        detail=f"missing all expected checkpoints: {expected}",
    )


def _check_required_text_encoder() -> CheckResult:
    for name in REQUIRED_TEXT_ENCODERS:
        path = _file_exists(_text_encoder_paths(name))
        if path is not None:
            return CheckResult(
                name="ltxv_text_encoder",
                ok=True,
                detail=f"found {name} at {path}",
            )
    expected = ", ".join(REQUIRED_TEXT_ENCODERS)
    return CheckResult(
        name="ltxv_text_encoder",
        ok=False,
        detail=f"missing required text encoder: {expected}",
    )


def _check_required_ipadapter_model() -> CheckResult:
    for name in REQUIRED_IPADAPTER_MODELS:
        path = _file_exists(_ipadapter_paths(name))
        if path is not None:
            return CheckResult(
                name="ipadapter_model",
                ok=True,
                detail=f"found {name} at {path}",
            )
    expected = ", ".join(REQUIRED_IPADAPTER_MODELS)
    return CheckResult(
        name="ipadapter_model",
        ok=False,
        detail=f"missing required ipadapter model: {expected}",
    )


def _check_required_plus_face_ipadapter_model() -> CheckResult:
    for name in REQUIRED_PLUS_FACE_IPADAPTER_MODELS:
        return _check_asset(
            name,
            _ipadapter_paths(name),
            result_name="ipadapter_plus_face_model",
            required=True,
            missing_detail="missing required plus-face ipadapter model",
        )
    raise RuntimeError("missing plus-face ipadapter model name")


def _check_optional_faceid_ipadapter_model() -> CheckResult:
    for name in OPTIONAL_FACEID_IPADAPTER_MODELS:
        return _check_asset(
            name,
            _ipadapter_paths(name),
            result_name="ipadapter_faceid_model",
            required=False,
            missing_detail="missing optional FaceID ipadapter asset",
        )
    raise RuntimeError("missing faceid ipadapter model name")


def _check_optional_faceid_lora_model() -> CheckResult:
    for name in OPTIONAL_FACEID_LORA_MODELS:
        return _check_asset(
            name,
            _loras_paths(name),
            result_name="ipadapter_faceid_lora",
            required=False,
            missing_detail="missing optional FaceID LoRA asset",
        )
    raise RuntimeError("missing faceid lora model name")


def _check_required_clip_vision() -> CheckResult:
    for name in REQUIRED_CLIP_VISION_MODELS:
        path = _file_exists(_clip_vision_paths(name))
        if path is not None:
            return CheckResult(
                name="clip_vision_model",
                ok=True,
                detail=f"found {name} at {path}",
            )
    expected = ", ".join(REQUIRED_CLIP_VISION_MODELS)
    return CheckResult(
        name="clip_vision_model",
        ok=False,
        detail=f"missing required clip vision model: {expected}",
    )


def _check_optional_noobai_checkpoint() -> CheckResult:
    for name in OPTIONAL_NOOBAI_CHECKPOINT_MODELS:
        return _check_asset(
            name,
            _checkpoint_only_paths(name),
            result_name="noobai_checkpoint",
            required=False,
            missing_detail="missing optional NoobAI-XL checkpoint",
        )
    raise RuntimeError("missing noobai checkpoint model name")


def _check_backend_executor_config() -> CheckResult:
    try:
        data = _fetch_json(f"{BACKEND_URL}/api/v1/animation/executor-config")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return CheckResult(
            name="backend_animation_executor",
            ok=False,
            detail=str(exc),
        )

    mode = data.get("mode")
    remote_base_url = data.get("remote_base_url")
    executor_key = data.get("executor_key")
    if mode != "remote_worker":
        return CheckResult(
            name="backend_animation_executor",
            ok=False,
            detail=f"expected mode=remote_worker, got {mode}",
        )
    if remote_base_url != WORKER_URL:
        return CheckResult(
            name="backend_animation_executor",
            ok=False,
            detail=f"expected remote_base_url={WORKER_URL}, got {remote_base_url}",
        )
    return CheckResult(
        name="backend_animation_executor",
        ok=True,
        detail=f"mode={mode}, executor_key={executor_key}, remote_base_url={remote_base_url}",
    )


def _check_comfy_node(name: str) -> CheckResult:
    try:
        data = _fetch_json(f"{COMFY_URL}/object_info/{name}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return CheckResult(name=f"node:{name}", ok=False, detail=str(exc))
    return CheckResult(
        name=f"node:{name}",
        ok=name in data,
        detail="available" if name in data else "missing",
    )


def run() -> int:
    checks: list[CheckResult] = [
        _api_check(
            "backend_health",
            f"{BACKEND_URL}/api/v1/system/health",
            "backend reachable",
        ),
        _check_backend_executor_config(),
        _api_check(
            "worker_health",
            f"{WORKER_URL}/healthz",
            "worker reachable",
        ),
        _api_check(
            "comfyui_health",
            f"{COMFY_URL}/system_stats",
            "comfyui reachable",
        ),
        _check_required_checkpoint(),
        _check_required_text_encoder(),
        _check_required_ipadapter_model(),
        _check_required_plus_face_ipadapter_model(),
        _check_required_clip_vision(),
        _check_optional_faceid_ipadapter_model(),
        _check_optional_faceid_lora_model(),
        _check_optional_noobai_checkpoint(),
    ]
    checks.extend(_check_comfy_node(name) for name in REQUIRED_NODES)
    checks.extend(_check_comfy_node(name) for name in REQUIRED_IPADAPTER_NODES)

    any_failures = False
    print("Local Animation Preflight")
    print(f"root: {ROOT_DIR}")
    for check in checks:
        if check.ok:
            label = "PASS"
        elif check.required:
            label = "FAIL"
        else:
            label = "WARN"
        if check.required and not check.ok:
            any_failures = True
        print(f"[{label}] {check.name}: {check.detail}")

    return 1 if any_failures else 0


if __name__ == "__main__":
    sys.exit(run())
