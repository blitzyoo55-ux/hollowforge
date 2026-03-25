"""ADetailer-like face fix using YOLO (preferred) or OpenCV haarcascade fallback."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

import cv2
from PIL import Image, ImageDraw

from app.config import settings
from app.db import get_db
from app.services.comfyui_client import ComfyUIClient
from app.services.workflow_builder import build_adetail_workflow

logger = logging.getLogger(__name__)

_YOLO_MODEL_PATH = (
    settings.PINOKIO_PRIMARY_PEER_DIR / "ultralytics" / "bbox" / "face_yolov8n.pt"
    if settings.PINOKIO_PRIMARY_PEER_DIR is not None
    else None
)

_yolo_model = None


def _get_yolo_model():
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    try:
        from ultralytics import YOLO  # type: ignore
        if _YOLO_MODEL_PATH and _YOLO_MODEL_PATH.is_file():
            _yolo_model = YOLO(str(_YOLO_MODEL_PATH))
            logger.info("ADetailer: loaded YOLO face model from %s", _YOLO_MODEL_PATH)
            return _yolo_model
    except Exception as e:
        logger.debug("ADetailer: YOLO unavailable (%s), will use haarcascade", e)
    return None


def _iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    a_x2 = ax + aw
    a_y2 = ay + ah
    b_x2 = bx + bw
    b_y2 = by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(a_x2, b_x2)
    inter_y2 = min(a_y2, b_y2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    if inter_w == 0 or inter_h == 0:
        return 0.0

    inter_area = inter_w * inter_h
    area_a = aw * ah
    area_b = bw * bh
    union = area_a + area_b - inter_area
    if union <= 0:
        return 0.0
    return inter_area / union


def _dedupe_boxes(
    boxes: list[tuple[int, int, int, int]],
    iou_threshold: float = 0.35,
) -> list[tuple[int, int, int, int]]:
    if not boxes:
        return []

    # Keep larger boxes first so profile/frontal overlaps collapse into one face region.
    ordered = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
    kept: list[tuple[int, int, int, int]] = []
    for box in ordered:
        if any(_iou(box, prev) >= iou_threshold for prev in kept):
            continue
        kept.append(box)
    return kept


def _expand_box(
    box: tuple[int, int, int, int],
    image_w: int,
    image_h: int,
    margin_ratio: float = 0.3,
) -> tuple[int, int, int, int]:
    x, y, w, h = box
    mx = int(round(w * margin_ratio))
    my = int(round(h * margin_ratio))

    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(image_w, x + w + mx)
    y2 = min(image_h, y + h + my)
    return x1, y1, max(1, x2 - x1), max(1, y2 - y1)


def _detect_faces_yolo(image_path: Path) -> list[tuple[int, int, int, int]] | None:
    """YOLO-based face detection. Returns boxes or None if unavailable."""
    model = _get_yolo_model()
    if model is None:
        return None
    try:
        results = model(str(image_path), conf=0.25, iou=0.35, verbose=False)
        if not results:
            return []
        boxes: list[tuple[int, int, int, int]] = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            boxes.append((x1, y1, max(1, x2 - x1), max(1, y2 - y1)))
        return boxes
    except Exception as e:
        logger.warning("ADetailer: YOLO detection failed (%s), falling back", e)
        return None


def _detect_faces_haarcascade(image_path: Path) -> list[tuple[int, int, int, int]]:
    """OpenCV haarcascade face detection fallback."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Failed to read image: {image_path}")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    image_h, image_w = gray.shape[:2]

    frontal = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
    )
    profile = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_profileface.xml"
    )
    if frontal.empty() or profile.empty():
        raise RuntimeError("Failed to load OpenCV haarcascade models")

    frontal_faces = frontal.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    profile_faces = profile.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    mirrored = cv2.flip(gray, 1)
    mirrored_faces = profile.detectMultiScale(mirrored, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    boxes: list[tuple[int, int, int, int]] = []
    for x, y, w, h in frontal_faces:
        boxes.append((int(x), int(y), int(w), int(h)))
    for x, y, w, h in profile_faces:
        boxes.append((int(x), int(y), int(w), int(h)))
    for x, y, w, h in mirrored_faces:
        mirrored_x = image_w - int(x) - int(w)
        boxes.append((mirrored_x, int(y), int(w), int(h)))
    return boxes


def detect_faces(image_path: Path) -> list[tuple[int, int, int, int]]:
    """
    Return list of (x, y, w, h) bounding boxes for detected faces.
    Tries YOLO (face_yolov8n) first; falls back to haarcascade.
    Each bbox is expanded by 30% margin for better inpainting coverage.
    """
    yolo_boxes = _detect_faces_yolo(image_path)
    if yolo_boxes is not None:
        raw_boxes = yolo_boxes
        logger.debug("ADetailer: YOLO detected %d face(s)", len(raw_boxes))
    else:
        raw_boxes = _detect_faces_haarcascade(image_path)
        logger.debug("ADetailer: haarcascade detected %d face(s)", len(raw_boxes))

    with Image.open(image_path) as _img:
        image_w, image_h = _img.size

    deduped = _dedupe_boxes(raw_boxes)
    if not deduped:
        return []

    expanded = [_expand_box(box, image_w, image_h, margin_ratio=0.3) for box in deduped]
    return _dedupe_boxes(expanded)


def create_face_mask(
    image_size: tuple[int, int],
    faces: list[tuple[int, int, int, int]],
) -> Image.Image:
    """Return black/white PIL mask (white = inpaint area)."""
    mask = Image.new("L", image_size, 0)
    if not faces:
        return mask

    draw = ImageDraw.Draw(mask)
    for x, y, w, h in faces:
        draw.rectangle((x, y, x + w, y + h), fill=255)
    return mask


def _load_image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def _save_png(image: Image.Image, output_path: Path) -> None:
    image.save(output_path, format="PNG")


async def run_adetail(
    generation_id: str,
    comfyui_client: ComfyUIClient,
    denoise: float = 0.4,
    steps: int = 20,
) -> Path:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM generations WHERE id = ?",
            (generation_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise ValueError(f"Generation {generation_id} not found")
    if row.get("status") != "completed":
        raise ValueError("Only completed generations can be face-fixed")

    source_rel = row.get("upscaled_image_path") or row.get("image_path")
    if not source_rel:
        raise ValueError("Generation has no source image")

    source_path = (settings.DATA_DIR / source_rel).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Source image not found: {source_path}")

    faces = await asyncio.to_thread(detect_faces, source_path)
    if not faces:
        raise ValueError("No faces detected in image")

    image_size = await asyncio.to_thread(_load_image_size, source_path)
    mask = await asyncio.to_thread(create_face_mask, image_size, faces)

    tmp_mask_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_mask_file.close()
    tmp_mask_path = Path(tmp_mask_file.name)

    try:
        await asyncio.to_thread(_save_png, mask, tmp_mask_path)

        source_upload_name = await comfyui_client.upload_image(
            str(source_path),
            f"hollowforge_adetail_source_{generation_id}.png",
        )
        mask_upload_name = await comfyui_client.upload_image(
            str(tmp_mask_path),
            f"hollowforge_adetail_mask_{generation_id}.png",
        )

        workflow, save_node_id = build_adetail_workflow(
            source_image_filename=source_upload_name,
            mask_image_filename=mask_upload_name,
            checkpoint=row.get("checkpoint") or settings.DEFAULT_CHECKPOINT,
            positive_prompt=row.get("prompt") or "",
            negative_prompt=row.get("negative_prompt") or "",
            seed=int(row.get("seed") or 0),
            denoise=denoise,
            steps=steps,
            cfg=float(row.get("cfg")) if row.get("cfg") is not None else 7.0,
            sampler=row.get("sampler") or "euler",
            scheduler=row.get("scheduler") or "normal",
            filename_prefix=f"hollowforge_adetail_{generation_id[:8]}",
        )

        prompt_id = await comfyui_client.submit_prompt(workflow)
        images = await comfyui_client.wait_for_completion(prompt_id, save_node_id)
        if not images:
            raise RuntimeError("ComfyUI adetail finished without output images")

        image_bytes = await comfyui_client.download_image(images[0])

        out_dir = settings.IMAGES_DIR / "adetailed"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{generation_id}.png"
        out_path.write_bytes(image_bytes)
        out_rel = f"images/adetailed/{generation_id}.png"

        async with get_db() as db:
            await db.execute(
                """UPDATE generations
                   SET adetailed_path = ?, error_message = NULL
                   WHERE id = ?""",
                (out_rel, generation_id),
            )
            await db.commit()

        logger.info("ADetail completed for %s (%d face region(s))", generation_id, len(faces))
        return out_path
    finally:
        tmp_mask_path.unlink(missing_ok=True)
