#!/usr/bin/env python3
"""Validate the standalone safe upscale runner on representative samples."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.services.safe_upscale_runner import run_safe_upscale  # noqa: E402
from app.services.upscaler import (  # noqa: E402
    classify_checkpoint_upscale_profile,
    recommend_upscale_model,
    resolve_upscale_model_path,
)


TARGET_COUNTS = {
    "anime-illustration": 2,
    "general-realistic": 2,
    "hybrid-clean": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit-per-profile",
        type=int,
        default=2,
        help="Fallback sample cap for any profile not explicitly listed.",
    )
    return parser.parse_args()


def make_panel(image: Image.Image, label: str, target_width: int = 320) -> Image.Image:
    image = image.convert("RGB")
    scale = target_width / image.width
    resized = image.resize(
        (target_width, max(1, int(image.height * scale))),
        Image.Resampling.LANCZOS,
    )
    label_h = 24
    panel = Image.new("RGB", (resized.width, resized.height + label_h), "#111111")
    panel.paste(resized, (0, label_h))
    draw = ImageDraw.Draw(panel)
    draw.rectangle((0, 0, resized.width, label_h), fill="#1d1d1d")
    draw.text((8, 7), label, fill="#f2f2f2", font=ImageFont.load_default())
    return panel


def pad_to_height(image: Image.Image, target_height: int) -> Image.Image:
    if image.height == target_height:
        return image
    padded = Image.new("RGB", (image.width, target_height), "#111111")
    padded.paste(image, (0, 0))
    return padded


def write_contact_sheet(rows: list[tuple[Image.Image, Image.Image]], output_path: Path) -> None:
    gap = 20
    strips: list[Image.Image] = []
    for left, right in rows:
        row_height = max(left.height, right.height)
        left = pad_to_height(left, row_height)
        right = pad_to_height(right, row_height)
        width = left.width + right.width + gap
        strip = Image.new("RGB", (width, row_height), "#0b0b0b")
        strip.paste(left, (0, 0))
        strip.paste(right, (left.width + gap, 0))
        strips.append(strip)

    sheet_width = max(strip.width for strip in strips)
    sheet_height = sum(strip.height for strip in strips) + gap * (len(strips) - 1)
    sheet = Image.new("RGB", (sheet_width, sheet_height), "#0b0b0b")
    y = 0
    for strip in strips:
        sheet.paste(strip, (0, y))
        y += strip.height + gap
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="PNG", optimize=True)


def select_samples(limit_per_profile: int) -> list[sqlite3.Row]:
    query = """
        SELECT id, checkpoint, image_path, created_at
        FROM generations
        WHERE status = 'completed'
          AND image_path IS NOT NULL
        ORDER BY created_at DESC
    """
    picked: list[sqlite3.Row] = []
    used_ids: set[str] = set()
    counts: dict[str, int] = {}
    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()
    for row in rows:
        profile = classify_checkpoint_upscale_profile(row["checkpoint"])
        max_for_profile = TARGET_COUNTS.get(profile, limit_per_profile)
        if counts.get(profile, 0) >= max_for_profile:
            continue
        if row["id"] in used_ids:
            continue
        picked.append(row)
        used_ids.add(row["id"])
        counts[profile] = counts.get(profile, 0) + 1
        if all(counts.get(profile, 0) >= target for profile, target in TARGET_COUNTS.items()):
            break
    return picked


def main() -> int:
    args = parse_args()
    samples = select_samples(args.limit_per_profile)
    output_dir = settings.DATA_DIR / "validation" / "upscale_safe_runner"
    output_dir.mkdir(parents=True, exist_ok=True)

    rows_for_sheet: list[tuple[Image.Image, Image.Image]] = []
    summary: list[dict[str, object]] = []
    available_models = None

    for sample in samples:
        profile = classify_checkpoint_upscale_profile(sample["checkpoint"])
        model_name, recommended_profile = recommend_upscale_model(
            sample["checkpoint"],
            available_models=available_models,
        )
        if not model_name:
            raise RuntimeError(f"No local upscale model available for {sample['id']}")

        model_path = resolve_upscale_model_path(model_name)
        source_path = settings.DATA_DIR / sample["image_path"]
        result_bytes = run_safe_upscale(source_path, model_path)

        safe_path = output_dir / f"{sample['id']}_safe.png"
        safe_path.write_bytes(result_bytes)

        with Image.open(source_path) as source_img:
            safe_img = Image.open(BytesIO(result_bytes))
            rows_for_sheet.append(
                (
                    make_panel(source_img, f"{sample['id'][:8]} original"),
                    make_panel(safe_img, f"{sample['id'][:8]} safe"),
                )
            )
            summary.append(
                {
                    "id": sample["id"],
                    "checkpoint": sample["checkpoint"],
                    "profile": profile,
                    "recommended_profile": recommended_profile,
                    "model": model_name,
                    "source_rel": sample["image_path"],
                    "safe_rel": str(safe_path.relative_to(settings.DATA_DIR)),
                    "source_size": [source_img.width, source_img.height],
                    "safe_size": [safe_img.width, safe_img.height],
                }
            )
            safe_img.close()

    contact_sheet = output_dir / "standalone_safe_contact_sheet_20260309.png"
    write_contact_sheet(rows_for_sheet, contact_sheet)
    result = {
        "samples": summary,
        "contact_sheet": str(contact_sheet.relative_to(settings.DATA_DIR)),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
