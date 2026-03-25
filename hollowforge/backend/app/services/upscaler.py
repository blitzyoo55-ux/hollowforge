"""Tile-based image upscaler using PyTorch on CPU."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from app.config import settings

logger = logging.getLogger(__name__)

_ANIME_HINTS = (
    "anime",
    "animayhem",
    "animagine",
    "illustrious",
    "illustrij",
    "wai",
    "pony",
    "noob",
    "hassaku",
    "autismmix",
    "prefect",
    "oneobsession",
    "obsession",
    "rxtr",
    "hentai",
    "akiumlumenill",
    "aam",
    "toon",
    "cartoon",
    "counterfeit",
    "anything",
)

_GENERAL_HINTS = (
    "realistic",
    "realvis",
    "realism",
    "realisticvision",
    "juggernaut",
    "epicrealism",
    "cyberrealistic",
    "photon",
    "majicmix",
    "zavy",
    "absolute",
    "lunar",
)

_HYBRID_HINTS = (
    "ponyrealism",
    "lumen",
)


def _iter_model_dirs() -> list[Path]:
    dirs = [p.expanduser() for p in settings.UPSCALE_MODELS_DIRS]
    peers_dir = settings.PINOKIO_PEERS_DIR.expanduser()
    if peers_dir.exists():
        for peer_dir in peers_dir.iterdir():
            if peer_dir.is_dir():
                dirs.append(peer_dir / "upscale_models")
    return dirs


def list_local_upscale_models() -> list[str]:
    """Return locally discoverable upscale model filenames."""
    model_names: set[str] = set()
    for base in _iter_model_dirs():
        if not base.exists():
            continue
        for pattern in ("*.safetensors", "*.pth", "*.pt", "*.ckpt", "*.bin"):
            for candidate in base.glob(pattern):
                if candidate.is_file():
                    model_names.add(candidate.name)
    return sorted(model_names, key=str.lower)


def resolve_upscale_model_path(model_name_or_path: str) -> Path:
    """Resolve an upscaler model name to an absolute path."""
    requested = Path(model_name_or_path).expanduser()
    if requested.is_file():
        return requested.resolve()

    model_name = requested.name
    for base in _iter_model_dirs():
        candidate = base / model_name
        if candidate.is_file():
            return candidate.resolve()

    target_lower = model_name.lower()
    for base in _iter_model_dirs():
        if not base.exists():
            continue
        for pattern in ("*.safetensors", "*.pth", "*.pt", "*.ckpt", "*.bin"):
            for candidate in base.glob(pattern):
                if candidate.name.lower() == target_lower:
                    return candidate.resolve()

    searched = ", ".join(str(p) for p in _iter_model_dirs())
    raise FileNotFoundError(
        f"Upscale model '{model_name_or_path}' not found. Searched: {searched}"
    )


def classify_checkpoint_upscale_profile(checkpoint: str | None) -> str:
    """Infer which upscale profile best matches a checkpoint family."""
    name = (checkpoint or "").lower()
    if any(hint in name for hint in _HYBRID_HINTS):
        return "hybrid-clean"
    if any(hint in name for hint in _ANIME_HINTS):
        return "anime-illustration"
    if any(hint in name for hint in _GENERAL_HINTS):
        return "general-realistic"
    return "general-clean"


def recommend_upscale_model(
    checkpoint: str | None,
    available_models: list[str] | None = None,
) -> tuple[str | None, str]:
    """Recommend the best available upscale model for a checkpoint."""
    available = (
        sorted(set(available_models), key=str.lower)
        if available_models is not None
        else list_local_upscale_models()
    )
    if not available:
        return None, classify_checkpoint_upscale_profile(checkpoint)

    profile = classify_checkpoint_upscale_profile(checkpoint)
    available_lower = {name.lower(): name for name in available}

    def pick(*candidates: str) -> str | None:
        for candidate in candidates:
            found = available_lower.get(candidate.lower())
            if found:
                return found
        return None

    if profile == "anime-illustration":
        return (
            pick(
                "RealESRGAN_x4plus_anime_6B.pth",
                "remacri_original.safetensors",
                "realesr-general-x4v3.pth",
            )
            or available[0],
            profile,
        )

    if profile == "hybrid-clean":
        return (
            pick(
                "remacri_original.safetensors",
                "realesr-general-x4v3.pth",
                "RealESRGAN_x4plus_anime_6B.pth",
            )
            or available[0],
            profile,
        )

    return (
        pick(
            "realesr-general-x4v3.pth",
            "remacri_original.safetensors",
            "RealESRGAN_x4plus_anime_6B.pth",
        )
        or available[0],
        profile,
    )


def recommend_upscale_mode(checkpoint: str | None) -> tuple[str, str]:
    """Recommend the safer user-facing upscale mode for a checkpoint family."""
    profile = classify_checkpoint_upscale_profile(checkpoint)
    if profile == "anime-illustration":
        return (
            "quality",
            "Anime / illustration checkpoints passed staged quality validation and can use Quality Upscale manually.",
        )
    if profile == "hybrid-clean":
        return (
            "safe",
            "Hybrid checkpoints currently favor Safe Upscale until more staged quality samples are validated.",
        )
    if profile == "general-realistic":
        return (
            "safe",
            "General / realistic checkpoints are not yet validated on the staged quality path in the current ComfyUI runtime.",
        )
    return (
        "safe",
        "Safe Upscale is the default recommendation for unclassified checkpoints.",
    )


class TileUpscaler:
    """Load an ESRGAN-style .safetensors model and upscale with tiling."""

    def __init__(self, model_path: Path):
        self.device = torch.device("cpu")
        self.model, self.scale = self._load_model(model_path)

    def _load_model(self, model_path: Path) -> tuple[torch.nn.Module, int]:
        from spandrel import ModelLoader

        descriptor = ModelLoader().load_from_file(str(model_path))
        model = descriptor.model.eval().to(self.device)
        scale = int(getattr(descriptor, "scale", None) or getattr(model, "scale", 4))
        logger.info("Loaded upscaler model %s (scale=%sx)", model_path, scale)
        return model, scale

    def upscale(
        self, image: Image.Image, tile_size: int = 512, overlap: int = 32
    ) -> Image.Image:
        if tile_size <= overlap:
            raise ValueError("tile_size must be greater than overlap")

        image = ImageOps.exif_transpose(image).convert("RGB")
        img_np = np.asarray(image, dtype=np.float32) / 255.0
        in_h, in_w, channels = img_np.shape
        out_h, out_w = in_h * self.scale, in_w * self.scale

        output = np.zeros((out_h, out_w, channels), dtype=np.float32)
        weights = np.zeros((out_h, out_w, 1), dtype=np.float32)

        step = tile_size - overlap
        with torch.inference_mode():
            for y in range(0, in_h, step):
                for x in range(0, in_w, step):
                    y_end = min(y + tile_size, in_h)
                    x_end = min(x + tile_size, in_w)
                    tile = img_np[y:y_end, x:x_end, :]

                    tile_tensor = (
                        torch.from_numpy(tile.transpose(2, 0, 1))
                        .unsqueeze(0)
                        .to(self.device)
                    )
                    result_tensor = self.model(tile_tensor)
                    result = result_tensor.squeeze(0).cpu().numpy().transpose(1, 2, 0)
                    result = np.clip(result, 0.0, 1.0)

                    out_y = y * self.scale
                    out_x = x * self.scale
                    tile_out_h, tile_out_w = result.shape[:2]

                    mask = np.ones((tile_out_h, tile_out_w), dtype=np.float32)
                    blend = max(1, overlap * self.scale)
                    blend_y = min(blend, tile_out_h)
                    blend_x = min(blend, tile_out_w)
                    ramp_y = np.linspace(0.0, 1.0, blend_y, endpoint=True, dtype=np.float32)
                    ramp_x = np.linspace(0.0, 1.0, blend_x, endpoint=True, dtype=np.float32)

                    if y > 0:
                        mask[:blend_y, :] *= ramp_y[:, None]
                    if x > 0:
                        mask[:, :blend_x] *= ramp_x[None, :]
                    if y_end < in_h:
                        mask[-blend_y:, :] *= ramp_y[::-1][:, None]
                    if x_end < in_w:
                        mask[:, -blend_x:] *= ramp_x[::-1][None, :]

                    mask3 = mask[:, :, None]
                    output[
                        out_y : out_y + tile_out_h, out_x : out_x + tile_out_w, :
                    ] += result * mask3
                    weights[
                        out_y : out_y + tile_out_h, out_x : out_x + tile_out_w, :
                    ] += mask3

        output /= np.maximum(weights, 1e-8)
        out_uint8 = np.clip(output * 255.0, 0, 255).astype(np.uint8)
        return Image.fromarray(out_uint8, mode="RGB")
