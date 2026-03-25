"""AI-based image quality assessment endpoints.

Endpoints:
    POST /api/v1/quality/analyze/{generation_id}  — analyze single image
    POST /api/v1/quality/analyze-batch            — batch process
    GET  /api/v1/quality/report                   — summary stats
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.db import get_db
from app.services.ai_quality_service import analyze_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["quality-ai"])
_has_all_tags_json_column: Optional[bool] = None

# Keywords that identify pixel-art checkpoints / LoRAs.
# When found in checkpoint name or any LoRA name, pixel_art_mode=True is passed
# to the quality scorer so style-specific tags are not penalised.
_PIXEL_ART_KEYWORDS = ("pixel", "pixelart", "pixel_art", "dot_art", "dotart", "8bit", "16bit")


def _detect_pixel_art(checkpoint: Optional[str], loras_json: Optional[str]) -> bool:
    """Return True if checkpoint or any LoRA name contains a pixel-art keyword."""
    sources: list[str] = []
    if checkpoint:
        sources.append(checkpoint.lower())
    if loras_json:
        try:
            loras = json.loads(loras_json)
            if isinstance(loras, list):
                for item in loras:
                    name = item if isinstance(item, str) else (item.get("name") or item.get("model") or "")
                    sources.append(str(name).lower())
        except (json.JSONDecodeError, TypeError):
            pass
    return any(kw in src for src in sources for kw in _PIXEL_ART_KEYWORDS)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AnalyzeResult(BaseModel):
    generation_id: str
    quality_ai_score: Optional[int]
    quality_score: Optional[int]  # blended score written to DB
    hand_count: int
    finger_anomaly: int
    quality_tags: list[str]
    wd14_bad_tags: list[str]
    wd14_good_tags: list[str]
    hands_finger_counts: list[int]
    scoring_mode: str
    aesthetic_raw: Optional[float]


class BatchRequest(BaseModel):
    limit: int = 200
    skip_analyzed: bool = True


class BatchResult(BaseModel):
    processed: int
    skipped: int
    errors: int


class QualityReport(BaseModel):
    total_analyzed: int
    anomaly_count: int
    anomaly_rate: float
    bad_tag_distribution: dict[str, int]
    score_histogram: dict[str, int]  # bucket -> count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_generation(db: Any, generation_id: str) -> dict:
    cursor = await db.execute(
        """SELECT id, image_path, quality_score, quality_ai_score, quality_tags,
                  hand_count, finger_anomaly, checkpoint, loras
           FROM generations WHERE id = ?""",
        (generation_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )
    return row


async def _supports_all_tags_json(db: Any) -> bool:
    """Check and cache whether generations.all_tags_json exists."""
    global _has_all_tags_json_column
    if _has_all_tags_json_column is not None:
        return _has_all_tags_json_column

    cursor = await db.execute("PRAGMA table_info(generations)")
    columns = await cursor.fetchall()
    _has_all_tags_json_column = any(col.get("name") == "all_tags_json" for col in columns)
    return _has_all_tags_json_column


async def _run_and_store(
    db: Any,
    generation_id: str,
    image_path: str,
    pixel_art_mode: bool = False,
) -> AnalyzeResult:
    """Run AI analysis and persist results. Returns AnalyzeResult."""
    result = await analyze_image(image_path, pixel_art_mode=pixel_art_mode)

    ai_score = result["quality_ai_score"]
    wd14 = result["wd14"]
    hands = result["hands"]

    # Fetch existing quality_score to blend
    cursor = await db.execute(
        "SELECT quality_score FROM generations WHERE id = ?", (generation_id,)
    )
    row = await cursor.fetchone()
    existing_score = row["quality_score"] if row else None

    if existing_score is not None and ai_score is not None:
        blended = int(existing_score * 0.4 + ai_score * 0.6)
    elif ai_score is not None:
        blended = ai_score
    else:
        blended = existing_score

    quality_tags_json = json.dumps(result["quality_tags"])
    all_tags_json = json.dumps(wd14.get("all_tags", {}), ensure_ascii=False)

    if await _supports_all_tags_json(db):
        await db.execute(
            """UPDATE generations
               SET quality_tags      = ?,
                   all_tags_json     = ?,
                   quality_ai_score  = ?,
                   hand_count        = ?,
                   finger_anomaly    = ?,
                   quality_score     = ?
               WHERE id = ?""",
            (
                quality_tags_json,
                all_tags_json,
                ai_score,
                result["hand_count"],
                result["finger_anomaly"],
                blended,
                generation_id,
            ),
        )
    else:
        await db.execute(
            """UPDATE generations
               SET quality_tags      = ?,
                   quality_ai_score  = ?,
                   hand_count        = ?,
                   finger_anomaly    = ?,
                   quality_score     = ?
               WHERE id = ?""",
            (
                quality_tags_json,
                ai_score,
                result["hand_count"],
                result["finger_anomaly"],
                blended,
                generation_id,
            ),
        )
    await db.commit()

    return AnalyzeResult(
        generation_id=generation_id,
        quality_ai_score=ai_score,
        quality_score=blended,
        hand_count=result["hand_count"],
        finger_anomaly=result["finger_anomaly"],
        quality_tags=result["quality_tags"],
        wd14_bad_tags=wd14.get("bad_tags", []),
        wd14_good_tags=wd14.get("good_tags", []),
        hands_finger_counts=hands.get("finger_counts", []),
        scoring_mode=result.get("scoring_mode", "legacy_tag_count"),
        aesthetic_raw=result.get("aesthetic_raw"),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/api/v1/quality/analyze/{generation_id}",
    response_model=AnalyzeResult,
)
async def analyze_single(generation_id: str) -> AnalyzeResult:
    """Analyze a single generation's image with WD14 + MediaPipe and store results."""
    async with get_db() as db:
        row = await _fetch_generation(db, generation_id)

        image_path = row.get("image_path")
        if not image_path:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Generation {generation_id} has no image_path",
            )

        pixel_art_mode = _detect_pixel_art(row.get("checkpoint"), row.get("loras"))
        return await _run_and_store(db, generation_id, image_path, pixel_art_mode=pixel_art_mode)


@router.post(
    "/api/v1/quality/analyze-batch",
    response_model=BatchResult,
)
async def analyze_batch(body: BatchRequest) -> BatchResult:
    """Batch-analyze completed generations. Skips already-analyzed ones if skip_analyzed=true."""
    async with get_db() as db:
        if body.skip_analyzed:
            cursor = await db.execute(
                """SELECT id, image_path, checkpoint, loras FROM generations
                   WHERE status = 'completed'
                     AND image_path IS NOT NULL
                     AND quality_ai_score IS NULL
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (body.limit,),
            )
        else:
            cursor = await db.execute(
                """SELECT id, image_path, checkpoint, loras FROM generations
                   WHERE status = 'completed'
                     AND image_path IS NOT NULL
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (body.limit,),
            )

        rows = await cursor.fetchall()

    processed = 0
    skipped = 0
    errors = 0

    for row in rows:
        gen_id = row["id"]
        image_path = row["image_path"]
        if not image_path:
            skipped += 1
            continue
        pixel_art_mode = _detect_pixel_art(row.get("checkpoint"), row.get("loras"))
        try:
            async with get_db() as db:
                await _run_and_store(db, gen_id, image_path, pixel_art_mode=pixel_art_mode)
            processed += 1
        except Exception as exc:
            logger.error("Batch analyze error for %s: %s", gen_id, exc, exc_info=True)
            errors += 1

    return BatchResult(processed=processed, skipped=skipped, errors=errors)


@router.get(
    "/api/v1/quality/report",
    response_model=QualityReport,
)
async def quality_report() -> QualityReport:
    """Return summary stats for AI-analyzed generations."""
    async with get_db() as db:
        # Total analyzed
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM generations WHERE quality_ai_score IS NOT NULL"
        )
        row = await cursor.fetchone()
        total_analyzed = row["cnt"] if row else 0

        # Anomaly count
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM generations WHERE finger_anomaly = 1"
        )
        row = await cursor.fetchone()
        anomaly_count = row["cnt"] if row else 0

        anomaly_rate = (anomaly_count / total_analyzed) if total_analyzed > 0 else 0.0

        # All quality_tags JSON for distribution
        cursor = await db.execute(
            "SELECT quality_tags FROM generations WHERE quality_tags IS NOT NULL"
        )
        tag_rows = await cursor.fetchall()

        bad_tag_distribution: dict[str, int] = {}
        for tag_row in tag_rows:
            try:
                tags = json.loads(tag_row["quality_tags"] or "[]")
                for tag in tags:
                    bad_tag_distribution[tag] = bad_tag_distribution.get(tag, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        # Score histogram (buckets: 0-9, 10-19, ..., 90-100)
        cursor = await db.execute(
            "SELECT quality_ai_score FROM generations WHERE quality_ai_score IS NOT NULL"
        )
        score_rows = await cursor.fetchall()

        score_histogram: dict[str, int] = {}
        for score_row in score_rows:
            s = score_row["quality_ai_score"]
            bucket_start = (s // 10) * 10
            # Last bucket is "90-100" (inclusive) to match frontend HISTOGRAM_BUCKETS.
            # Scores 90-100 all fall into this bucket.
            if bucket_start >= 90:
                bucket_key = "90-100"
            else:
                bucket_key = f"{bucket_start}-{bucket_start + 9}"
            score_histogram[bucket_key] = score_histogram.get(bucket_key, 0) + 1

    return QualityReport(
        total_analyzed=total_analyzed,
        anomaly_count=anomaly_count,
        anomaly_rate=round(anomaly_rate, 4),
        bad_tag_distribution=bad_tag_distribution,
        score_histogram=score_histogram,
    )
