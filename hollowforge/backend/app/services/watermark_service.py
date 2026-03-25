"""Watermark rendering utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

from app.config import settings as app_settings

_DEFAULT_TEXT = "Lab-XX"
_DEFAULT_POSITION = "bottom-right"
_DEFAULT_OPACITY = 0.6
_DEFAULT_FONT_SIZE = 36
_DEFAULT_PADDING = 20
_DEFAULT_COLOR = "#FFFFFF"
_VALID_POSITIONS = {"top-left", "top-right", "bottom-left", "bottom-right", "center"}


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_image_path(image_path: str) -> Path:
    candidate = Path(image_path)
    if candidate.is_absolute():
        return candidate
    return (app_settings.DATA_DIR / candidate).resolve()


def _load_font(font_size: int) -> ImageFont.ImageFont:
    for font_name in ("DejaVuSans.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _resolve_position(
    position: str,
    image_width: int,
    image_height: int,
    text_width: int,
    text_height: int,
    padding: int,
) -> tuple[int, int]:
    if position == "top-left":
        return padding, padding
    if position == "top-right":
        return max(padding, image_width - text_width - padding), padding
    if position == "bottom-left":
        return padding, max(padding, image_height - text_height - padding)
    if position == "center":
        return (image_width - text_width) // 2, (image_height - text_height) // 2
    # default: bottom-right
    return (
        max(padding, image_width - text_width - padding),
        max(padding, image_height - text_height - padding),
    )


def _normalize_settings(settings: dict[str, Any]) -> dict[str, Any]:
    text = str(settings.get("text") or _DEFAULT_TEXT).strip() or _DEFAULT_TEXT
    position = str(settings.get("position") or _DEFAULT_POSITION).strip()
    if position not in _VALID_POSITIONS:
        position = _DEFAULT_POSITION

    opacity = min(max(_to_float(settings.get("opacity"), _DEFAULT_OPACITY), 0.0), 1.0)
    font_size = max(8, _to_int(settings.get("font_size"), _DEFAULT_FONT_SIZE))
    padding = max(0, _to_int(settings.get("padding"), _DEFAULT_PADDING))
    color = str(settings.get("color") or _DEFAULT_COLOR).strip() or _DEFAULT_COLOR

    return {
        "text": text,
        "position": position,
        "opacity": opacity,
        "font_size": font_size,
        "padding": padding,
        "color": color,
    }


def apply_watermark(image_path: str, settings: dict[str, Any]) -> str:
    """Apply a text watermark and return the stored relative image path."""
    source_path = _resolve_image_path(image_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source image not found: {source_path}")

    cfg = _normalize_settings(settings)
    font = _load_font(cfg["font_size"])

    with Image.open(source_path) as source_image:
        image = ImageOps.exif_transpose(source_image).convert("RGBA")
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        text_bbox = draw.textbbox((0, 0), cfg["text"], font=font)
        text_width = max(1, text_bbox[2] - text_bbox[0])
        text_height = max(1, text_bbox[3] - text_bbox[1])
        x, y = _resolve_position(
            cfg["position"],
            image.width,
            image.height,
            text_width,
            text_height,
            cfg["padding"],
        )

        try:
            red, green, blue = ImageColor.getrgb(cfg["color"])
        except ValueError:
            red, green, blue = ImageColor.getrgb(_DEFAULT_COLOR)
        alpha = int(cfg["opacity"] * 255)
        draw.text((x, y), cfg["text"], font=font, fill=(red, green, blue, alpha))

        watermarked = Image.alpha_composite(image, overlay).convert("RGB")

    output_dir = app_settings.IMAGES_DIR / "watermarked"
    output_dir.mkdir(parents=True, exist_ok=True)
    image_stem = Path(image_path).stem
    output_file = output_dir / f"{image_stem}.jpg"
    watermarked.save(str(output_file), "JPEG", quality=95, optimize=True)
    return f"images/watermarked/{image_stem}.jpg"
