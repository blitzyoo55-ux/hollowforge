#!/usr/bin/env python3
"""Validate HollowForge safe upscale output against known broken samples."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.services.safe_upscale_runner import run_safe_upscale  # noqa: E402
from app.services.upscaler import resolve_upscale_model_path  # noqa: E402


DEFAULT_IDS = [
    "c996c2ef-049c-4afd-b816-40cc29ceaac9",
    "8c3fb245-658b-4c03-8b51-db25aa2d2d31",
    "0e6c5bb8-d9c3-4366-abcf-da9939c0432c",
]


@dataclass
class Sample:
    gen_id: str
    source_rel: str
    broken_rel: str
    source_path: Path
    broken_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ids",
        nargs="+",
        default=DEFAULT_IDS,
        help="Generation IDs to validate",
    )
    parser.add_argument(
        "--model",
        default="remacri_original.safetensors",
        help="Upscale model filename or full path",
    )
    return parser.parse_args()


def load_samples(ids: list[str]) -> list[Sample]:
    query = (
        "SELECT id, image_path, upscaled_image_path "
        "FROM generations WHERE id = ?"
    )
    samples: list[Sample] = []
    with sqlite3.connect(settings.DB_PATH) as conn:
        for gen_id in ids:
            row = conn.execute(query, (gen_id,)).fetchone()
            if row is None:
                raise RuntimeError(f"Generation not found: {gen_id}")
            _, source_rel, broken_rel = row
            if not source_rel or not broken_rel:
                raise RuntimeError(f"Generation missing paths: {gen_id}")
            source_path = (settings.DATA_DIR / source_rel).resolve()
            broken_path = (settings.DATA_DIR / broken_rel).resolve()
            if not source_path.exists():
                raise FileNotFoundError(f"Missing source image: {source_path}")
            if not broken_path.exists():
                raise FileNotFoundError(f"Missing broken image: {broken_path}")
            samples.append(
                Sample(
                    gen_id=gen_id,
                    source_rel=source_rel,
                    broken_rel=broken_rel,
                    source_path=source_path,
                    broken_path=broken_path,
                )
            )
    return samples


def make_panel(image: Image.Image, label: str, target_width: int) -> Image.Image:
    image = image.convert("RGB")
    scale = target_width / image.width
    resized = image.resize(
        (target_width, max(1, int(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    font = ImageFont.load_default()
    label_h = 24
    panel = Image.new("RGB", (resized.width, resized.height + label_h), "#111111")
    panel.paste(resized, (0, label_h))
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, resized.width, label_h), fill="#1d1d1d")
    draw.text((8, 7), label, fill="#f2f2f2", font=font)
    return panel


def pad_to_height(image: Image.Image, target_height: int) -> Image.Image:
    if image.height == target_height:
        return image
    padded = Image.new("RGB", (image.width, target_height), "#111111")
    padded.paste(image, (0, 0))
    return padded


def write_contact_sheet(
    rows: list[tuple[Image.Image, Image.Image, Image.Image]],
    output_path: Path,
) -> None:
    gap = 20
    all_rows: list[Image.Image] = []
    for row in rows:
        row_height = max(img.height for img in row)
        padded = [pad_to_height(img, row_height) for img in row]
        row_width = sum(img.width for img in padded) + gap * (len(padded) - 1)
        strip = Image.new("RGB", (row_width, row_height), "#0b0b0b")
        x = 0
        for image in padded:
            strip.paste(image, (x, 0))
            x += image.width + gap
        all_rows.append(strip)

    sheet_width = max(img.width for img in all_rows)
    sheet_height = sum(img.height for img in all_rows) + gap * (len(all_rows) - 1)
    sheet = Image.new("RGB", (sheet_width, sheet_height), "#0b0b0b")
    y = 0
    for row_image in all_rows:
        sheet.paste(row_image, (0, y))
        y += row_image.height + gap
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)


def main() -> int:
    args = parse_args()
    model_path = resolve_upscale_model_path(args.model)
    samples = load_samples(args.ids)

    output_dir = settings.DATA_DIR / "validation" / "upscale_safe"
    output_dir.mkdir(parents=True, exist_ok=True)
    contact_rows: list[tuple[Image.Image, Image.Image, Image.Image]] = []
    summary: list[dict[str, object]] = []

    for sample in samples:
        result_bytes = run_safe_upscale(sample.source_path, model_path)
        safe_path = output_dir / f"{sample.gen_id}_safe.png"
        safe_path.write_bytes(result_bytes)

        with Image.open(sample.source_path) as src_img, Image.open(sample.broken_path) as broken_img:
            safe_img = Image.open(BytesIO(result_bytes))
            contact_rows.append(
                (
                    make_panel(src_img, f"{sample.gen_id[:8]} original", 360),
                    make_panel(broken_img, f"{sample.gen_id[:8]} broken", 360),
                    make_panel(safe_img, f"{sample.gen_id[:8]} safe", 360),
                )
            )
            summary.append(
                {
                    "id": sample.gen_id,
                    "source_rel": sample.source_rel,
                    "broken_rel": sample.broken_rel,
                    "safe_rel": str(safe_path.relative_to(settings.DATA_DIR)),
                    "source_size": [src_img.width, src_img.height],
                    "broken_size": [broken_img.width, broken_img.height],
                    "safe_size": [safe_img.width, safe_img.height],
                }
            )
            safe_img.close()

    contact_path = output_dir / "safe_upscale_contact_sheet_20260308.png"
    write_contact_sheet(contact_rows, contact_path)

    result = {
        "model_path": str(model_path),
        "contact_sheet": str(contact_path.relative_to(settings.DATA_DIR)),
        "samples": summary,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
