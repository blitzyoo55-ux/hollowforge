"""
Quality scoring service for auto-evaluation of generated images.

Score breakdown (0-100):
- steps >= 28: +15
- steps >= 32: +5 bonus (total +20)
- adetail completed (adetailed_path not null): +20
- upscale completed (upscaled_image_path not null): +15
- hiresfix completed (hiresfix_path not null): +10
- high resolution (width*height >= 1024*1024): +10
- is_favorite: +25
Total max: 100

Default APPROVE_THRESHOLD = 40
(steps-only = 20, favorite+steps = 45 → threshold 40 catches favorites)
"""

from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite

APPROVE_THRESHOLD = 40


def _compute_score(row: dict) -> int:
    """Compute quality score from a generation row dict."""
    score = 0

    steps = row.get("steps") or 0
    if steps >= 28:
        score += 15
    if steps >= 32:
        score += 5  # bonus for high-step generations

    if row.get("adetailed_path"):
        score += 20

    if row.get("upscaled_image_path"):
        score += 15

    if row.get("hiresfix_path"):
        score += 10

    width = row.get("width") or 0
    height = row.get("height") or 0
    if width * height >= 1024 * 1024:
        score += 10

    if row.get("is_favorite"):
        score += 25

    return score


async def calculate_quality_score(db: aiosqlite.Connection, generation_id: str) -> int:
    """Calculate and persist quality score for a single generation.

    Returns the computed score (0-100). Writes the score to the DB.
    """
    cursor = await db.execute(
        """SELECT id, steps, adetailed_path, upscaled_image_path, hiresfix_path,
                  width, height, is_favorite
           FROM generations WHERE id = ?""",
        (generation_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return 0

    score = _compute_score(row)

    await db.execute(
        "UPDATE generations SET quality_score = ? WHERE id = ?",
        (score, generation_id),
    )
    await db.commit()
    return score


async def update_quality_scores(db: aiosqlite.Connection, limit: int = 100) -> int:
    """Recalculate quality scores for the most recent `limit` completed generations.

    Returns count of rows updated.
    """
    cursor = await db.execute(
        """SELECT id, steps, adetailed_path, upscaled_image_path, hiresfix_path,
                  width, height, is_favorite
           FROM generations
           WHERE status = 'completed'
           ORDER BY created_at DESC
           LIMIT ?""",
        (limit,),
    )
    rows = await cursor.fetchall()

    updated = 0
    for row in rows:
        score = _compute_score(row)
        await db.execute(
            "UPDATE generations SET quality_score = ? WHERE id = ?",
            (score, row["id"]),
        )
        updated += 1

    await db.commit()
    return updated


async def auto_approve(db: aiosqlite.Connection, threshold: int = APPROVE_THRESHOLD) -> int:
    """Set publish_approved=1 for all completed generations with quality_score >= threshold
    that are still pending (publish_approved=0).

    Returns count of rows approved.
    """
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute(
        """UPDATE generations
           SET publish_approved = 1, curated_at = ?
           WHERE status = 'completed'
             AND quality_score IS NOT NULL
             AND quality_score >= ?
             AND publish_approved = 0""",
        (now, threshold),
    )
    count = cursor.rowcount
    await db.commit()
    return count
