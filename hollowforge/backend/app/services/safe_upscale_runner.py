"""Standalone safe upscale runner with in-process model caching."""

from __future__ import annotations

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.services.upscaler import TileUpscaler


@lru_cache(maxsize=4)
def _get_upscaler(model_path: str) -> TileUpscaler:
    return TileUpscaler(Path(model_path))


def run_safe_upscale(
    source_image_path: Path,
    model_path: Path,
    *,
    tile_size: int = 512,
    overlap: int = 32,
) -> bytes:
    """Upscale a local image with the cached CPU runner and return PNG bytes."""
    upscaler = _get_upscaler(str(model_path.resolve()))
    with Image.open(source_image_path) as source:
        upscaled = upscaler.upscale(source, tile_size=tile_size, overlap=overlap)
    out = BytesIO()
    upscaled.save(out, format="PNG", optimize=True)
    return out.getvalue()
