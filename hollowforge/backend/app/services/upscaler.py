"""Tile-based image upscaler using PyTorch on CPU."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

from app.config import settings

logger = logging.getLogger(__name__)


def _iter_model_dirs() -> list[Path]:
    dirs = [p.expanduser() for p in settings.UPSCALE_MODELS_DIRS]
    peers_dir = settings.PINOKIO_PEERS_DIR.expanduser()
    if peers_dir.exists():
        for peer_dir in peers_dir.iterdir():
            if peer_dir.is_dir():
                dirs.append(peer_dir / "upscale_models")
    return dirs


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
        for candidate in base.glob("*.safetensors"):
            if candidate.name.lower() == target_lower:
                return candidate.resolve()

    searched = ", ".join(str(p) for p in _iter_model_dirs())
    raise FileNotFoundError(
        f"Upscale model '{model_name_or_path}' not found. Searched: {searched}"
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
