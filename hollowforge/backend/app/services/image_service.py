"""Image storage, thumbnailing, and workflow persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from app.config import settings


async def save_generation_image(
    image_bytes: bytes, generation_id: str
) -> tuple[str, str, str]:
    """Persist a generated image to disk.

    Returns relative paths (image_path, thumbnail_path, workflow_path) suitable
    for storing in the database and serving via StaticFiles.
    """
    now = datetime.now(timezone.utc)
    date_subdir = now.strftime("%Y/%m/%d")

    # --- Full image ---
    img_dir = settings.IMAGES_DIR / date_subdir
    img_dir.mkdir(parents=True, exist_ok=True)
    img_file = img_dir / f"{generation_id}.png"
    img_file.write_bytes(image_bytes)
    image_rel = f"images/{date_subdir}/{generation_id}.png"

    # --- Thumbnail (512px width, proportional height) ---
    settings.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    thumb_file = settings.THUMBS_DIR / f"{generation_id}_w512.jpg"
    img = Image.open(BytesIO(image_bytes))
    thumb_width = 512
    ratio = thumb_width / img.width
    thumb_height = int(img.height * ratio)
    thumb = img.resize((thumb_width, thumb_height), Image.LANCZOS)
    thumb.save(str(thumb_file), "JPEG", quality=85)
    thumb_rel = f"thumbs/{generation_id}_w512.jpg"

    # Workflow path placeholder (actual workflow saved separately)
    wf_rel = f"workflows/{generation_id}.json"

    return image_rel, thumb_rel, wf_rel


def save_workflow(workflow: dict[str, Any], generation_id: str) -> str:
    """Persist the ComfyUI workflow JSON to disk. Returns relative path."""
    settings.WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    wf_file = settings.WORKFLOWS_DIR / f"{generation_id}.json"
    wf_file.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
    return f"workflows/{generation_id}.json"
