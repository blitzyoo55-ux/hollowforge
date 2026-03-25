#!/usr/bin/env python3
"""Batch re-analysis for AI quality scoring.

Usage:
    ./.venv/bin/python scripts/reanalyze_ai_quality.py --limit 200
    ./.venv/bin/python scripts/reanalyze_ai_quality.py --only-scored --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
import sys

import aiosqlite

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import settings
from app.services.ai_quality_service import analyze_image


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reanalyze generations with AI quality")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=settings.DB_PATH,
        help=f"SQLite DB path (default: {settings.DB_PATH})",
    )
    parser.add_argument("--limit", type=int, default=200, help="Max rows to process")
    parser.add_argument("--offset", type=int, default=0, help="Row offset")
    parser.add_argument(
        "--only-scored",
        action="store_true",
        help="Reanalyze only rows that already have quality_ai_score",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run inference without writing results",
    )
    parser.add_argument(
        "--commit-every",
        type=int,
        default=20,
        help="Commit interval for DB updates",
    )
    return parser.parse_args()


async def _supports_all_tags_json(db: aiosqlite.Connection) -> bool:
    cursor = await db.execute("PRAGMA table_info(generations)")
    rows = await cursor.fetchall()
    return any(row.get("name") == "all_tags_json" for row in rows)


_PIXEL_ART_KEYWORDS = ("pixel", "pixelart", "pixel_art", "dot_art", "dotart", "8bit", "16bit")


def _detect_pixel_art(checkpoint: str | None, loras_json: str | None) -> bool:
    sources: list[str] = []
    if checkpoint:
        sources.append(checkpoint.lower())
    if loras_json:
        try:
            import json
            loras = json.loads(loras_json)
            if isinstance(loras, list):
                for item in loras:
                    name = item if isinstance(item, str) else (item.get("name") or item.get("model") or "")
                    sources.append(str(name).lower())
        except Exception:
            pass
    return any(kw in src for src in sources for kw in _PIXEL_ART_KEYWORDS)


async def _fetch_targets(db: aiosqlite.Connection, only_scored: bool, limit: int, offset: int) -> list[dict]:
    where = ["status = 'completed'", "image_path IS NOT NULL"]
    if only_scored:
        where.append("quality_ai_score IS NOT NULL")

    sql = f"""
        SELECT id, image_path, quality_score, checkpoint, loras
        FROM generations
        WHERE {' AND '.join(where)}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    cursor = await db.execute(sql, (limit, offset))
    return await cursor.fetchall()


async def _update_row(
    db: aiosqlite.Connection,
    generation_id: str,
    result: dict,
    existing_quality_score: int | None,
    has_all_tags_json: bool,
) -> None:
    ai_score = result.get("quality_ai_score")
    if existing_quality_score is not None and ai_score is not None:
        blended = int(existing_quality_score * 0.4 + ai_score * 0.6)
    elif ai_score is not None:
        blended = ai_score
    else:
        blended = existing_quality_score

    wd14 = result.get("wd14", {})
    quality_tags_json = json.dumps(result.get("quality_tags", []), ensure_ascii=False)
    all_tags_json = json.dumps(wd14.get("all_tags", {}), ensure_ascii=False)

    if has_all_tags_json:
        await db.execute(
            """
            UPDATE generations
               SET quality_tags      = ?,
                   all_tags_json     = ?,
                   quality_ai_score  = ?,
                   hand_count        = ?,
                   finger_anomaly    = ?,
                   quality_score     = ?
             WHERE id = ?
            """,
            (
                quality_tags_json,
                all_tags_json,
                ai_score,
                result.get("hand_count"),
                result.get("finger_anomaly"),
                blended,
                generation_id,
            ),
        )
    else:
        await db.execute(
            """
            UPDATE generations
               SET quality_tags      = ?,
                   quality_ai_score  = ?,
                   hand_count        = ?,
                   finger_anomaly    = ?,
                   quality_score     = ?
             WHERE id = ?
            """,
            (
                quality_tags_json,
                ai_score,
                result.get("hand_count"),
                result.get("finger_anomaly"),
                blended,
                generation_id,
            ),
        )


async def main() -> None:
    args = parse_args()

    db = await aiosqlite.connect(str(args.db_path))
    db.row_factory = _dict_factory  # type: ignore[assignment]

    try:
        rows = await _fetch_targets(
            db,
            only_scored=args.only_scored,
            limit=args.limit,
            offset=args.offset,
        )
        has_all_tags_json = await _supports_all_tags_json(db)

        print(
            f"targets={len(rows)} only_scored={args.only_scored} "
            f"dry_run={args.dry_run} all_tags_json={has_all_tags_json}"
        )

        processed = 0
        errors = 0

        for row in rows:
            generation_id = row["id"]
            image_path = row["image_path"]
            existing_quality_score = row.get("quality_score")

            pixel_art_mode = _detect_pixel_art(row.get("checkpoint"), row.get("loras"))
            try:
                result = await analyze_image(image_path, pixel_art_mode=pixel_art_mode)
                processed += 1

                if not args.dry_run:
                    await _update_row(
                        db,
                        generation_id=generation_id,
                        result=result,
                        existing_quality_score=existing_quality_score,
                        has_all_tags_json=has_all_tags_json,
                    )
                    if processed % max(1, args.commit_every) == 0:
                        await db.commit()

                if processed % 10 == 0:
                    print(
                        f"processed={processed} errors={errors} "
                        f"latest_score={result.get('quality_ai_score')} "
                        f"mode={result.get('scoring_mode')}"
                    )
            except Exception as exc:
                errors += 1
                print(f"error generation_id={generation_id}: {exc}")

        if not args.dry_run:
            await db.commit()

        print(f"done processed={processed} errors={errors}")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
