"""
AI-based image quality assessment:
- WD14 SwinV2 Tagger v3: detects quality/anatomy tags
- Aesthetic predictor (lazy-loaded): predicts visual quality score
- MediaPipe Hands: finger count anomaly detection
"""

from __future__ import annotations

import csv
import logging
import os
import socket
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Keep MediaPipe in CPU mode for headless/server environments.
os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")

# Data directory for resolving relative image paths stored in DB
DATA_DIR = Path(__file__).resolve().parents[3] / "data"

# MediaPipe hand landmarker model path (downloaded once)
_MP_MODEL_PATH = Path(__file__).resolve().parents[3] / "backend" / "hand_landmarker.task"

# ---------------------------------------------------------------------------
# Backend detection (ONNX preferred over torch/timm)
# ---------------------------------------------------------------------------

try:
    import onnxruntime as ort  # type: ignore

    USE_ONNX = True
    logger.info("WD14: Using ONNX Runtime backend")
except ImportError:
    USE_ONNX = False
    logger.info("WD14: ONNX Runtime not available, will use torch/timm fallback")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WD14_REPO = "SmilingWolf/wd-swinv2-tagger-v3"
WD14_MODEL_FILE = "model.onnx"
WD14_TAGS_FILE = "selected_tags.csv"

# Input size for SwinV2
WD14_IMAGE_SIZE = 448

# Tag confidence threshold
WD14_THRESHOLD = 0.35

# Aesthetic model candidates
AESTHETIC_PRIMARY_REPO = "shyamag/aesthetic-predictor-v2-5"
AESTHETIC_ALT_REPO = "discus0434/aesthetic-predictor-v2-5"
AESTHETIC_FALLBACK_REPO = "cafeai/cafe_aesthetic"
AESTHETIC_MODEL_REPOS = (
    AESTHETIC_PRIMARY_REPO,
    AESTHETIC_ALT_REPO,
    AESTHETIC_FALLBACK_REPO,
)
AESTHETIC_ONNX_FILES = (
    "model.onnx",
    "aesthetic.onnx",
    "aesthetic_predictor.onnx",
)

# CLIP normalization (used by CLIP ViT-L/14 family)
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)

QUALITY_BAD_TAGS: set[str] = {
    # Anatomy
    "bad_anatomy",
    "bad_proportions",
    "extra_limbs",
    "missing_limbs",
    "deformed",
    "mutated",
    "malformed_limbs",
    "long_neck",
    # Hands/fingers
    "bad_hands",
    "extra_fingers",
    "missing_fingers",
    "fused_fingers",
    "too_many_fingers",
    "poorly_drawn_hands",
    "mutated_hands",
    # Face
    "bad_face",
    "poorly_drawn_face",
    "ugly",
    "duplicate_faces",
    # General quality
    "worst_quality",
    "low_quality",
    "normal_quality",
    "jpeg_artifacts",
    "blurry",
    "pixelated",
    # Latex/mask specific
    "poorly_drawn",
}

# Tags that represent intentional artistic style in pixel art — not defects.
# When pixel_art_mode=True these are excluded from bad-tag penalty calculation.
QUALITY_BAD_TAGS_PIXEL_ART_EXEMPT: set[str] = {
    "pixelated",
    "jpeg_artifacts",
    "blurry",
    "low_quality",
    "normal_quality",
}

QUALITY_GOOD_TAGS: set[str] = {
    "best_quality",
    "high_quality",
    "masterpiece",
    "detailed",
    "absurdres",
    "highres",
}

# ---------------------------------------------------------------------------
# Module-level singletons (lazy-loaded)
# ---------------------------------------------------------------------------

_wd14_session: Optional[object] = None  # ort.InferenceSession when ONNX
_wd14_torch_model: Optional[object] = None  # timm model when torch
_wd14_tags: Optional[list[str]] = None
_wd14_load_attempted: bool = False

_aesthetic_predictor: Optional[Callable[[Image.Image], float]] = None
_aesthetic_backend: Optional[str] = None
_aesthetic_repo: Optional[str] = None
_aesthetic_load_attempted: bool = False

_mp_hands: Optional[object] = None  # mp.tasks.vision.HandLandmarker instance
_mp_load_attempted: bool = False
_hf_online_checked: bool = False
_hf_online: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _download_wd14() -> tuple[Path, Path]:
    """Download WD14 model and tags via HuggingFace Hub. Returns (model_path, tags_path)."""
    model_path = _hf_download_cached_or_remote(WD14_REPO, WD14_MODEL_FILE)
    tags_path = _hf_download_cached_or_remote(WD14_REPO, WD14_TAGS_FILE)
    return model_path, tags_path


def _is_hf_online() -> bool:
    """Best-effort DNS check to avoid repeated long network retries when offline."""
    global _hf_online_checked, _hf_online
    if _hf_online_checked:
        return _hf_online

    _hf_online_checked = True
    try:
        socket.getaddrinfo("huggingface.co", 443)
        _hf_online = True
    except OSError:
        _hf_online = False
    return _hf_online


def _hf_download_cached_or_remote(repo_id: str, filename: str) -> Path:
    """Download file from HF, preferring local cache and skipping remote retries when offline."""
    from huggingface_hub import hf_hub_download  # type: ignore

    try:
        return Path(
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_files_only=True,
            )
        )
    except Exception:
        if not _is_hf_online():
            raise RuntimeError(
                f"HuggingFace offline and not cached: {repo_id}/{filename}"
            )
        return Path(hf_hub_download(repo_id=repo_id, filename=filename))


def _download_first_existing_file(repo_id: str, candidates: tuple[str, ...]) -> Optional[Path]:
    """Try downloading candidate files and return the first successful path."""
    for filename in candidates:
        try:
            return _hf_download_cached_or_remote(repo_id=repo_id, filename=filename)
        except Exception:
            continue
    return None


def _load_tags(tags_path: Path) -> list[str]:
    """Load tag list from selected_tags.csv. Returns list ordered by tag index."""
    tags: list[str] = []
    with open(tags_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tags.append(row["name"])
    return tags


def _resolve_image_path(image_path: str) -> Path:
    """Resolve an image_path (possibly relative to DATA_DIR) to an absolute Path."""
    p = Path(image_path)
    if p.is_absolute():
        return p
    return DATA_DIR / p


def _preprocess_image(image_path: str) -> np.ndarray:
    """Load and preprocess image for WD14 inference.

    Returns float32 array of shape (1, H, W, 3) in RGB order, values [0, 1].
    ONNX model expects NHWC layout.
    """
    img = Image.open(_resolve_image_path(image_path)).convert("RGB")
    # Resize with padding to maintain aspect ratio (pad white)
    canvas = Image.new("RGB", (WD14_IMAGE_SIZE, WD14_IMAGE_SIZE), (255, 255, 255))
    img.thumbnail((WD14_IMAGE_SIZE, WD14_IMAGE_SIZE), Image.LANCZOS)
    offset = (
        (WD14_IMAGE_SIZE - img.width) // 2,
        (WD14_IMAGE_SIZE - img.height) // 2,
    )
    canvas.paste(img, offset)
    arr = np.array(canvas, dtype=np.float32) / 255.0
    # WD14 ONNX expects BGR
    arr = arr[:, :, ::-1]
    return arr[np.newaxis, :]  # (1, 448, 448, 3)


def _ensure_wd14_loaded() -> bool:
    """Load WD14 model and tags into module-level singletons. Returns True on success."""
    global _wd14_session, _wd14_torch_model, _wd14_tags, _wd14_load_attempted

    if _wd14_load_attempted:
        return _wd14_tags is not None

    _wd14_load_attempted = True

    try:
        logger.info("WD14: Downloading/loading model from HuggingFace Hub...")
        model_path, tags_path = _download_wd14()
        _wd14_tags = _load_tags(tags_path)
        logger.info("WD14: Loaded %d tags", len(_wd14_tags))

        if USE_ONNX:
            import onnxruntime as ort  # type: ignore

            # CPU only — CoreML causes inference failures with WD14 SwinV2 on Apple Silicon
            providers = ["CPUExecutionProvider"]
            _wd14_session = ort.InferenceSession(str(model_path), providers=providers)
            logger.info("WD14: ONNX session created (providers=%s)", providers)
        else:
            import timm  # type: ignore
            import torch  # type: ignore

            _wd14_torch_model = timm.create_model(
                "swinv2_base_window12to24_192to384.ms_in22k_ft_in1k",
                pretrained=False,
                num_classes=len(_wd14_tags),
            )
            # Load weights from downloaded ONNX path is not directly usable with timm.
            # We rely on timm's pre-trained weights as a best-effort fallback.
            _wd14_torch_model.eval()  # type: ignore[union-attr]
            logger.warning(
                "WD14: torch/timm path active — note: tag predictions may be "
                "inaccurate without matching weights. ONNX Runtime is recommended."
            )

        return True

    except Exception as exc:
        logger.error("WD14: Failed to load model: %s", exc, exc_info=True)
        return False


def _run_wd14_onnx(arr: np.ndarray) -> np.ndarray:
    """Run inference with ONNX Runtime. Returns raw scores array."""
    input_name = _wd14_session.get_inputs()[0].name  # type: ignore[union-attr]
    outputs = _wd14_session.run(None, {input_name: arr})  # type: ignore[union-attr]
    return outputs[0][0]  # shape: (num_tags,)


def _run_wd14_torch(arr: np.ndarray) -> np.ndarray:
    """Run inference with torch/timm. Returns raw scores array."""
    import torch  # type: ignore

    # timm expects NCHW, float, RGB
    tensor = torch.from_numpy(arr).permute(0, 3, 1, 2)  # NHWC → NCHW
    # Convert BGR back to RGB
    tensor = tensor[:, [2, 1, 0], :, :]
    with torch.no_grad():
        logits = _wd14_torch_model(tensor)  # type: ignore[misc]
        scores = torch.sigmoid(logits).numpy()[0]
    return scores


def _compute_bad_tag_penalty(bad_tags: list[str], pixel_art_mode: bool = False) -> int:
    """Compute cumulative penalty from WD14 quality-negative tags.

    When pixel_art_mode=True, tags in QUALITY_BAD_TAGS_PIXEL_ART_EXEMPT are skipped
    because they describe intentional pixel-art style characteristics, not defects.
    """
    penalty = 0
    for tag in bad_tags:
        if pixel_art_mode and tag in QUALITY_BAD_TAGS_PIXEL_ART_EXEMPT:
            continue
        if tag == "worst_quality":
            penalty += 30
        elif tag == "low_quality":
            penalty += 15
        else:
            penalty += 10
    return penalty


def _compute_ai_score_legacy(
    bad_tags: list[str], good_tags: list[str], all_tags: dict[str, float],
    pixel_art_mode: bool = False,
) -> int:
    """Legacy 0-100 quality score from WD14 tag diversity (fallback mode)."""
    _ = good_tags  # retained for compatibility and possible future tuning

    # Tag diversity as base quality signal
    tag_count = len(all_tags)
    base = min(90, 65 + tag_count * 1)
    base = max(65, base)

    # Bad tag penalties
    penalty = _compute_bad_tag_penalty(bad_tags, pixel_art_mode=pixel_art_mode)
    score = base - min(penalty, 50)

    return max(0, min(100, score))


def _compute_ai_score_aesthetic(
    aesthetic_raw_1_to_10: float, bad_tags: list[str], has_finger_anomaly: bool,
    pixel_art_mode: bool = False,
) -> int:
    """Compute quality score using aesthetic predictor + penalties."""
    base = round(aesthetic_raw_1_to_10 * 10)  # 10-100 intended range
    penalty = _compute_bad_tag_penalty(bad_tags, pixel_art_mode=pixel_art_mode)
    if has_finger_anomaly:
        penalty += 10
    return max(0, min(100, base - penalty))


def _infer_onnx_layout_and_size(input_shape: list[object]) -> tuple[str, int]:
    """Infer ONNX image input layout and size from model input shape."""
    layout = "NCHW"
    size = 224

    if len(input_shape) != 4:
        return layout, size

    c1 = input_shape[1]
    c_last = input_shape[3]
    h_nchw = input_shape[2]
    h_nhwc = input_shape[1]

    if isinstance(c_last, int) and c_last == 3:
        layout = "NHWC"
        if isinstance(h_nhwc, int) and h_nhwc > 0:
            size = h_nhwc
    else:
        layout = "NCHW"
        if isinstance(c1, int) and c1 != 3 and isinstance(c_last, int) and c_last == 3:
            layout = "NHWC"
        if isinstance(h_nchw, int) and h_nchw > 0:
            size = h_nchw

    return layout, size


def _preprocess_aesthetic_onnx(img: Image.Image, layout: str, size: int) -> np.ndarray:
    """Preprocess image for CLIP-style aesthetic ONNX models."""
    image = img.convert("RGB").resize((size, size), Image.BICUBIC)
    arr = np.asarray(image, dtype=np.float32) / 255.0
    arr = (arr - CLIP_MEAN) / CLIP_STD
    if layout == "NHWC":
        return arr[np.newaxis, ...]
    # Default: NCHW
    return np.transpose(arr, (2, 0, 1))[np.newaxis, ...]


def _distribution_to_expected_score(logits_or_probs: np.ndarray) -> float:
    """Convert class logits/probabilities to expected score over 1..N bins."""
    vec = np.asarray(logits_or_probs, dtype=np.float32).reshape(-1)
    if vec.size == 0:
        raise ValueError("empty model output")
    if vec.size == 1:
        return float(vec[0])

    vec_sum = float(np.sum(vec))
    if np.all(vec >= 0.0) and abs(vec_sum - 1.0) <= 0.05:
        probs = vec / (vec_sum + 1e-8)
    else:
        shifted = vec - np.max(vec)
        exp = np.exp(shifted)
        denom = float(np.sum(exp)) + 1e-8
        probs = exp / denom

    bins = np.arange(1, vec.size + 1, dtype=np.float32)
    return float(np.sum(probs * bins))


def _normalize_aesthetic_score(raw_score: float, repo_id: Optional[str]) -> float:
    """Normalize raw aesthetic score into 1-10 scale.

    cafeai/cafe_aesthetic is a binary classifier (not_aesthetic vs aesthetic).
    _distribution_to_expected_score returns an expected bin in [1, 2].
    To recover P(aesthetic) ∈ [0, 1]: subtract 1.0, then scale to [0, 10].
    Example: raw=1.71 → P(aesthetic)=0.71 → score=7.1
    """
    if not np.isfinite(raw_score):
        raise ValueError(f"invalid aesthetic score: {raw_score}")

    # cafeai/cafe_aesthetic: binary model → expected bin in [1, 2].
    # Map [1, 2] → [0, 1] → [0, 10].
    if repo_id == AESTHETIC_FALLBACK_REPO:
        p_aesthetic = max(0.0, min(1.0, raw_score - 1.0))
        return float(p_aesthetic * 10.0)

    # Heuristic normalization for mixed checkpoints.
    if raw_score <= 1.1:
        return float(max(0.0, raw_score) * 10.0)
    if raw_score > 10.5 and raw_score <= 100.0:
        return float(raw_score / 10.0)
    return float(max(1.0, min(10.0, raw_score)))


def _load_aesthetic_onnx(repo_id: str) -> bool:
    """Try loading aesthetic predictor as ONNX from a repo."""
    global _aesthetic_predictor, _aesthetic_backend, _aesthetic_repo

    if not USE_ONNX:
        return False

    model_path = _download_first_existing_file(repo_id, AESTHETIC_ONNX_FILES)
    if model_path is None:
        return False

    try:
        import onnxruntime as ort  # type: ignore

        providers = ["CPUExecutionProvider"]
        session = ort.InferenceSession(str(model_path), providers=providers)
        input_meta = session.get_inputs()[0]
        layout, size = _infer_onnx_layout_and_size(list(input_meta.shape))
        input_name = input_meta.name

        def _predict(img: Image.Image) -> float:
            arr = _preprocess_aesthetic_onnx(img, layout=layout, size=size)
            output = session.run(None, {input_name: arr})[0]
            return _distribution_to_expected_score(np.asarray(output))

        _aesthetic_predictor = _predict
        _aesthetic_backend = "onnxruntime"
        _aesthetic_repo = repo_id
        logger.info(
            "Aesthetic: loaded ONNX model from %s (layout=%s size=%d providers=%s)",
            repo_id,
            layout,
            size,
            providers,
        )
        return True
    except Exception as exc:
        logger.warning(
            "Aesthetic: ONNX load failed for %s: %s", repo_id, exc, exc_info=True
        )
        return False


def _load_aesthetic_transformers(repo_id: str) -> bool:
    """Try loading aesthetic predictor via transformers image-classification head."""
    global _aesthetic_predictor, _aesthetic_backend, _aesthetic_repo

    try:
        import torch  # type: ignore
        from transformers import (  # type: ignore
            AutoImageProcessor,
            AutoModelForImageClassification,
        )
    except Exception:
        return False

    try:
        processor = AutoImageProcessor.from_pretrained(repo_id)
        model = AutoModelForImageClassification.from_pretrained(repo_id)
        model.eval()

        def _predict(img: Image.Image) -> float:
            inputs = processor(images=img, return_tensors="pt")
            with torch.no_grad():
                outputs = model(**inputs)
            return _distribution_to_expected_score(
                outputs.logits.detach().cpu().numpy()
            )

        _aesthetic_predictor = _predict
        _aesthetic_backend = "transformers"
        _aesthetic_repo = repo_id
        logger.info("Aesthetic: loaded transformers model from %s", repo_id)
        return True
    except Exception as exc:
        logger.warning(
            "Aesthetic: transformers load failed for %s: %s", repo_id, exc, exc_info=True
        )
        return False


def _ensure_aesthetic_loaded() -> bool:
    """Load aesthetic predictor lazily (ONNX preferred, then transformers)."""
    global _aesthetic_load_attempted
    if _aesthetic_load_attempted:
        return _aesthetic_predictor is not None

    _aesthetic_load_attempted = True

    for repo_id in AESTHETIC_MODEL_REPOS:
        if _load_aesthetic_onnx(repo_id):
            return True

    for repo_id in AESTHETIC_MODEL_REPOS:
        if _load_aesthetic_transformers(repo_id):
            return True

    logger.warning(
        "Aesthetic: model unavailable; using legacy WD14 tag-count scoring fallback"
    )
    return False


def _predict_aesthetic_score(image_path: str) -> Optional[float]:
    """Predict aesthetic score in 1-10 range. Returns None if unavailable."""
    if not _ensure_aesthetic_loaded():
        return None

    try:
        img = Image.open(_resolve_image_path(image_path)).convert("RGB")
        raw = float(_aesthetic_predictor(img))  # type: ignore[misc]
        normalized = _normalize_aesthetic_score(raw, _aesthetic_repo)
        return round(normalized, 4)
    except Exception as exc:
        logger.warning(
            "Aesthetic: inference failed for %s: %s", image_path, exc, exc_info=True
        )
        return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


def analyze_image_wd14(image_path: str, pixel_art_mode: bool = False) -> dict:
    """Run WD14 tagger on image_path.

    Args:
        image_path: Path to the image file.
        pixel_art_mode: When True, style-related tags (pixelated, blurry, etc.) are
            excluded from bad-tag penalties because they are intentional in pixel art.

    Returns:
        {
            "bad_tags": list[str],
            "good_tags": list[str],
            "all_tags": dict[str, float],
            "quality_score": int,
            "aesthetic_raw": float | None,
            "scoring_mode": str,
            "aesthetic_backend": str | None,
            "aesthetic_repo": str | None,
            "pixel_art_mode": bool,
        }
    On model load failure returns an empty result with score=None.
    """
    empty = {
        "bad_tags": [],
        "good_tags": [],
        "all_tags": {},
        "quality_score": None,
        "aesthetic_raw": None,
        "scoring_mode": "legacy_tag_count",
        "aesthetic_backend": None,
        "aesthetic_repo": None,
        "pixel_art_mode": pixel_art_mode,
    }

    if not _ensure_wd14_loaded():
        logger.warning("WD14: Model not available, skipping analysis for %s", image_path)
        return empty

    try:
        arr = _preprocess_image(image_path)

        if USE_ONNX:
            scores = _run_wd14_onnx(arr)
        else:
            scores = _run_wd14_torch(arr)

        all_tags: dict[str, float] = {}
        bad_tags: list[str] = []
        good_tags: list[str] = []

        for tag, score in zip(_wd14_tags, scores):  # type: ignore[arg-type]
            score_f = float(score)
            if score_f >= WD14_THRESHOLD:
                all_tags[tag] = round(score_f, 4)
                if tag in QUALITY_BAD_TAGS:
                    bad_tags.append(tag)
                elif tag in QUALITY_GOOD_TAGS:
                    good_tags.append(tag)

        aesthetic_raw = _predict_aesthetic_score(image_path)
        if aesthetic_raw is not None:
            quality_score = _compute_ai_score_aesthetic(
                aesthetic_raw_1_to_10=aesthetic_raw,
                bad_tags=bad_tags,
                has_finger_anomaly=False,
                pixel_art_mode=pixel_art_mode,
            )
            scoring_mode = "aesthetic_predictor_pixel_art" if pixel_art_mode else "aesthetic_predictor"
        else:
            quality_score = _compute_ai_score_legacy(bad_tags, good_tags, all_tags, pixel_art_mode=pixel_art_mode)
            scoring_mode = "legacy_tag_count_pixel_art" if pixel_art_mode else "legacy_tag_count"

        logger.info(
            "WD14 [%s]: bad=%s good=%s score=%d mode=%s aesthetic=%s pixel_art=%s",
            Path(image_path).name,
            bad_tags,
            good_tags,
            quality_score,
            scoring_mode,
            aesthetic_raw,
            pixel_art_mode,
        )
        return {
            "bad_tags": bad_tags,
            "good_tags": good_tags,
            "all_tags": all_tags,
            "quality_score": quality_score,
            "aesthetic_raw": aesthetic_raw,
            "scoring_mode": scoring_mode,
            "aesthetic_backend": _aesthetic_backend,
            "aesthetic_repo": _aesthetic_repo,
            "pixel_art_mode": pixel_art_mode,
        }

    except Exception as exc:
        logger.error("WD14: Inference failed for %s: %s", image_path, exc, exc_info=True)
        return empty


def _ensure_mp_hands() -> bool:
    """Initialize MediaPipe HandLandmarker (Tasks API, v0.10+). Returns True on success."""
    global _mp_hands, _mp_load_attempted
    if _mp_hands is not None:
        return True
    if _mp_load_attempted:
        return False
    _mp_load_attempted = True
    try:
        import mediapipe as mp  # type: ignore
        from mediapipe.tasks import python as mp_python  # type: ignore
        from mediapipe.tasks.python import vision as mp_vision  # type: ignore

        if not _MP_MODEL_PATH.exists():
            logger.warning("MediaPipe: model not found at %s, skipping hand detection", _MP_MODEL_PATH)
            return False

        base_options = mp_python.BaseOptions(
            model_asset_path=str(_MP_MODEL_PATH),
            delegate=mp_python.BaseOptions.Delegate.CPU,
        )
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            num_hands=4,
            min_hand_detection_confidence=0.5,
            running_mode=mp_vision.RunningMode.IMAGE,
        )
        _mp_hands = mp_vision.HandLandmarker.create_from_options(options)
        logger.info("MediaPipe: HandLandmarker initialized (Tasks API v0.10+)")
        return True
    except Exception as exc:
        logger.error("MediaPipe: Failed to initialize HandLandmarker: %s", exc, exc_info=True)
        return False


def detect_hand_anomaly(image_path: str) -> dict:
    """Detect hands and count fingers using MediaPipe Tasks API (v0.10+).

    Returns:
        {
            "hand_count": int,
            "finger_counts": list[int],  # per hand
            "has_anomaly": bool,
        }
    Anomaly = any hand with finger_count < 4 or > 6.
    """
    result_empty = {"hand_count": 0, "finger_counts": [], "has_anomaly": False}

    if not _ensure_mp_hands():
        return result_empty

    try:
        import mediapipe as mp  # type: ignore
        import cv2  # type: ignore

        abs_path = str(_resolve_image_path(image_path))
        image_bgr = cv2.imread(abs_path)
        if image_bgr is None:
            logger.warning("MediaPipe: Could not load image %s", abs_path)
            return result_empty

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        mp_result = _mp_hands.detect(mp_image)  # type: ignore[union-attr]

        if not mp_result.hand_landmarks:
            return {"hand_count": 0, "finger_counts": [], "has_anomaly": False}

        # Finger tip/pip landmark indices
        FINGER_TIP_IDS = [4, 8, 12, 16, 20]
        FINGER_PIP_IDS = [3, 6, 10, 14, 18]

        hand_count = len(mp_result.hand_landmarks)
        finger_counts: list[int] = []

        for hand_landmarks in mp_result.hand_landmarks:
            lm = hand_landmarks  # list of NormalizedLandmark
            count = 0

            # Thumb: tip further from MCP than IP → extended
            thumb_tip = lm[4]
            thumb_ip = lm[3]
            thumb_mcp = lm[2]
            if abs(thumb_tip.x - thumb_mcp.x) > abs(thumb_ip.x - thumb_mcp.x) * 0.7:
                count += 1

            # Other 4 fingers: tip y < pip y → extended (y increases downward)
            for tip_id, pip_id in zip(FINGER_TIP_IDS[1:], FINGER_PIP_IDS[1:]):
                if lm[tip_id].y < lm[pip_id].y:
                    count += 1

            finger_counts.append(count)

        has_anomaly = any(c < 4 or c > 6 for c in finger_counts)

        logger.info(
            "MediaPipe [%s]: hands=%d fingers=%s anomaly=%s",
            Path(image_path).name,
            hand_count,
            finger_counts,
            has_anomaly,
        )

        return {
            "hand_count": hand_count,
            "finger_counts": finger_counts,
            "has_anomaly": has_anomaly,
        }

    except ImportError:
        logger.warning("MediaPipe/cv2 not available, skipping hand detection")
        return result_empty
    except Exception as exc:
        logger.error(
            "MediaPipe: Detection failed for %s: %s", image_path, exc, exc_info=True
        )
        return result_empty


async def analyze_image(image_path: str, pixel_art_mode: bool = False) -> dict:
    """Async wrapper: runs WD14 + MediaPipe in executor threads.

    Args:
        image_path: Path to the image file.
        pixel_art_mode: When True, style tags (pixelated, blurry, etc.) are excluded
            from bad-tag penalties. Set this for images generated with pixel-art models.

    Returns combined result dict:
        {
            "wd14": {...},
            "hands": {...},
            "quality_ai_score": int | None,
            "hand_count": int,
            "finger_anomaly": int,   # 0 or 1
            "quality_tags": list[str],  # merged bad + good tags
            "scoring_mode": str,
            "aesthetic_raw": float | None,
            "pixel_art_mode": bool,
        }
    """
    import asyncio

    wd14_result, hands_result = await asyncio.gather(
        asyncio.to_thread(analyze_image_wd14, image_path, pixel_art_mode),
        asyncio.to_thread(detect_hand_anomaly, image_path),
    )

    quality_tags = wd14_result["bad_tags"] + wd14_result["good_tags"]
    finger_anomaly = 1 if hands_result["has_anomaly"] else 0

    quality_ai_score = wd14_result.get("quality_score")
    aesthetic_raw = wd14_result.get("aesthetic_raw")
    if aesthetic_raw is not None:
        # Recompute final score with finger anomaly penalty included.
        quality_ai_score = _compute_ai_score_aesthetic(
            aesthetic_raw_1_to_10=float(aesthetic_raw),
            bad_tags=wd14_result.get("bad_tags", []),
            has_finger_anomaly=bool(finger_anomaly),
            pixel_art_mode=pixel_art_mode,
        )

    return {
        "wd14": wd14_result,
        "hands": hands_result,
        "quality_ai_score": quality_ai_score,
        "hand_count": hands_result["hand_count"],
        "finger_anomaly": finger_anomaly,
        "quality_tags": quality_tags,
        "scoring_mode": wd14_result.get("scoring_mode", "legacy_tag_count"),
        "aesthetic_raw": aesthetic_raw,
        "pixel_art_mode": pixel_art_mode,
    }
