"""Local model architecture detection and LoRA compatibility inference."""

from __future__ import annotations

import json
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings

_SAFE_EXTS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}
_INDEX_CACHE: dict[str, tuple[float, dict[str, Path]]] = {}
_SAFETENSORS_CACHE: dict[str, tuple[float, int, float, dict[str, Any], list[str]]] = {}


@dataclass
class LoraAnalysis:
    filename: str
    category: str
    default_strength: float
    compatible_checkpoints: list[str]
    architecture: str


def parse_compatible_checkpoints(raw: str | None) -> list[str] | None:
    """Parse JSON-encoded compatible checkpoint list from DB."""
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, list):
        return None
    return [str(v) for v in value]


def dump_compatible_checkpoints(values: list[str] | None) -> str | None:
    if values is None:
        return None
    return json.dumps(values, ensure_ascii=False)


def is_checkpoint_compatible(raw: str | None, checkpoint: str) -> bool:
    """Check if a checkpoint is compatible with a DB row compatibility payload."""
    compat = parse_compatible_checkpoints(raw)
    if compat is None:
        return True
    return checkpoint in compat


def clear_model_compatibility_cache() -> None:
    _INDEX_CACHE.clear()
    _SAFETENSORS_CACHE.clear()


def _iter_model_roots(kind: str) -> list[Path]:
    roots: list[Path] = []

    peers_dir = settings.PINOKIO_PEERS_DIR
    if peers_dir.exists():
        for peer in peers_dir.iterdir():
            if not peer.is_dir():
                continue
            candidate = peer / kind
            if candidate.exists() and candidate.is_dir():
                roots.append(candidate)

    comfy_models = Path.home() / "ComfyUI" / "models" / kind
    if comfy_models.exists() and comfy_models.is_dir():
        roots.append(comfy_models)

    return roots


def _build_model_index(kind: str) -> dict[str, Path]:
    """Build lookup index by basename and relative path for a model kind."""
    ttl = max(0.0, settings.MODEL_COMPATIBILITY_CACHE_TTL_SEC)
    if ttl > 0:
        cached = _INDEX_CACHE.get(kind)
        if cached is not None:
            expires_at, index = cached
            if expires_at > time.monotonic():
                return index
            _INDEX_CACHE.pop(kind, None)

    index: dict[str, Path] = {}
    for root in _iter_model_roots(kind):
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in _SAFE_EXTS:
                continue
            rel = path.relative_to(root).as_posix()
            # keep first seen path for stable behavior
            index.setdefault(path.name, path)
            index.setdefault(rel, path)

    if ttl > 0:
        _INDEX_CACHE[kind] = (time.monotonic() + ttl, index)
    return index


def _resolve_model_path(name: str, index: dict[str, Path]) -> Path | None:
    if name in index:
        return index[name]
    return index.get(Path(name).name)


def _read_safetensors(path: Path | None) -> tuple[dict[str, Any], list[str]]:
    if path is None or not path.exists() or path.suffix.lower() != ".safetensors":
        return {}, []

    try:
        stat = path.stat()
        cache_key = str(path)
        ttl = max(0.0, settings.MODEL_COMPATIBILITY_CACHE_TTL_SEC)
        if ttl > 0:
            cached = _SAFETENSORS_CACHE.get(cache_key)
            if cached is not None:
                expires_at, size, mtime, metadata, keys = cached
                if (
                    expires_at > time.monotonic()
                    and size == stat.st_size
                    and mtime == stat.st_mtime
                ):
                    return metadata, keys
                _SAFETENSORS_CACHE.pop(cache_key, None)

        with path.open("rb") as f:
            head = f.read(8)
            if len(head) != 8:
                return {}, []
            header_len = struct.unpack("<Q", head)[0]
            payload = f.read(header_len)
        obj = json.loads(payload)
        if not isinstance(obj, dict):
            return {}, []
        md = obj.get("__metadata__", {}) if isinstance(obj.get("__metadata__"), dict) else {}
        keys = [k for k in obj.keys() if k != "__metadata__"]
        if ttl > 0:
            _SAFETENSORS_CACHE[cache_key] = (
                time.monotonic() + ttl,
                stat.st_size,
                stat.st_mtime,
                md,
                keys,
            )
        return md, keys
    except Exception:
        return {}, []


def _detect_checkpoint_architecture(
    checkpoint_name: str,
    metadata: dict[str, Any],
    keys: list[str],
) -> str:
    arch = str(metadata.get("modelspec.architecture", "")).lower()
    lower_name = checkpoint_name.lower()

    if "flux" in arch:
        return "FLUX"

    if any(
        k.startswith("double_blocks.")
        or k.startswith("img_in.")
        or k.startswith("text_encoders.")
        for k in keys
    ):
        return "FLUX"

    if any(k.startswith("cond_stage_model.") for k in keys):
        return "SD1.5"

    if checkpoint_name == "svd_xt.safetensors" or any("open_clip.model.visual" in k for k in keys):
        return "SVD-XT"

    if any(k.startswith("conditioner.embedders.") for k in keys):
        return "SDXL-family"

    # filename fallback when file path is unresolved
    if "flux" in lower_name:
        return "FLUX"
    if "svd" in lower_name:
        return "SVD-XT"
    if "sdxl" in lower_name or "xl" in lower_name:
        return "SDXL-family"

    return "Unknown"


def _detect_lora_architecture(
    lora_name: str,
    metadata: dict[str, Any],
    keys: list[str],
) -> str:
    lower_name = lora_name.lower()
    arch = str(metadata.get("modelspec.architecture", "")).lower()
    base = str(metadata.get("ss_base_model_version", "")).lower()
    source_model = str(metadata.get("ss_sd_model_name", "")).lower()

    if any(k.startswith("diffusion_model.blocks.") for k in keys):
        return "WAN-I2V-14B"

    if "flux" in arch or "flux" in base:
        return "FLUX"

    if "stable-diffusion-xl" in arch or "sdxl" in base:
        return "SDXL"

    if any(k.startswith("lora_te1_") or k.startswith("lora_te2_") for k in keys):
        return "SDXL"

    # Frequent no-metadata SDXL pattern (e.g. DetailedEyes)
    if any("transformer_blocks_9" in k for k in keys):
        return "SDXL"

    if "stable-diffusion-v1-5" in source_model or "animefull-final-pruned" in source_model:
        return "SD1.5"

    if any(k.startswith("lora_te_") or k.startswith("lora_te_text_model_") for k in keys):
        return "SD1.5"

    # filename fallback when metadata/key patterns are insufficient
    if "wan" in lower_name and ("i2v" in lower_name or lower_name.startswith("wan-")):
        return "WAN-I2V-14B"
    if "flux" in lower_name:
        return "FLUX"
    if "sd1.5" in lower_name or "sd15" in lower_name or "v1-5" in lower_name:
        return "SD1.5"

    if lora_name.lower().endswith(".pt"):
        return "WAN-I2V-14B"

    return "Unknown"


def _infer_category(filename: str) -> str:
    name = filename.lower()
    if any(k in name for k in ("eyes", "detail", "detailer", "insertion")):
        return "eyes"
    if any(k in name for k in ("latex", "shiny", "catsuit", "material")):
        return "material"
    if any(k in name for k in ("gag", "harness", "ahegao", "areola", "nsfw", "leotard", "plump", "drool")):
        return "fetish"
    return "style"


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _suggest_default_strength(
    metadata: dict[str, Any],
    filename: str,
    architecture: str,
    category: str,
) -> float:
    lower = filename.lower()

    if architecture == "WAN-I2V-14B":
        base = 0.8
        lo, hi = 0.6, 1.0
    elif architecture == "SD1.5":
        if "ahegao" in lower:
            base = 0.65
            lo, hi = 0.45, 0.9
        else:
            base = 0.6
            lo, hi = 0.4, 0.85
    elif category == "eyes":
        base = 0.6
        lo, hi = 0.35, 0.85
    elif category == "material":
        base = 0.68
        lo, hi = 0.45, 0.95
    elif category == "fetish":
        base = 0.75
        lo, hi = 0.55, 1.0
    else:
        base = 0.7
        lo, hi = 0.5, 0.95

    dim = _as_float(metadata.get("ss_network_dim"))
    alpha = _as_float(metadata.get("ss_network_alpha"))
    if dim and dim > 0 and alpha is not None:
        ratio = alpha / dim
        if ratio <= 0.2:
            base += 0.1
        elif ratio <= 0.4:
            base += 0.06
        elif ratio >= 1.0:
            base -= 0.05

    return round(max(lo, min(hi, base)), 2)


def build_lora_compatibility_snapshot(
    checkpoints: list[str],
    lora_files: list[str],
) -> tuple[dict[str, str], dict[str, LoraAnalysis]]:
    """Infer checkpoint architectures and LoRA compatibility from local files."""
    checkpoint_index = _build_model_index("checkpoints")
    lora_index = _build_model_index("loras") if lora_files else {}

    checkpoint_arch: dict[str, str] = {}
    for checkpoint in checkpoints:
        checkpoint_path = _resolve_model_path(checkpoint, checkpoint_index)
        metadata, keys = _read_safetensors(checkpoint_path)
        checkpoint_arch[checkpoint] = _detect_checkpoint_architecture(
            checkpoint, metadata, keys
        )

    arch_map: dict[str, list[str]] = {
        "SDXL-family": [c for c, a in checkpoint_arch.items() if a == "SDXL-family"],
        "SD1.5": [c for c, a in checkpoint_arch.items() if a == "SD1.5"],
        "FLUX": [c for c, a in checkpoint_arch.items() if a == "FLUX"],
        "WAN-I2V-14B": [c for c, a in checkpoint_arch.items() if a == "WAN-I2V-14B"],
    }

    lora_analysis: dict[str, LoraAnalysis] = {}
    for lora in lora_files:
        lora_path = _resolve_model_path(lora, lora_index)
        metadata, keys = _read_safetensors(lora_path)
        architecture = _detect_lora_architecture(lora, metadata, keys)
        category = _infer_category(lora)
        default_strength = _suggest_default_strength(
            metadata, lora, architecture, category
        )

        if architecture == "SDXL":
            compatible = arch_map["SDXL-family"]
        elif architecture == "SD1.5":
            compatible = arch_map["SD1.5"]
        elif architecture == "FLUX":
            compatible = arch_map["FLUX"]
        elif architecture == "WAN-I2V-14B":
            compatible = arch_map["WAN-I2V-14B"]
        else:
            # Unknown adapters should stay visible until manually reviewed.
            compatible = list(checkpoints)

        lora_analysis[lora] = LoraAnalysis(
            filename=lora,
            category=category,
            default_strength=default_strength,
            compatible_checkpoints=compatible,
            architecture=architecture,
        )

    return checkpoint_arch, lora_analysis
