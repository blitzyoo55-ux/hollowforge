#!/usr/bin/env python3
"""Reject completed generations that violate single-subject expectations."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
QUEUE_RUNS_DIR = ROOT_DIR / "docs" / "queue_runs"
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.services.adetailer_service import detect_faces


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QC a completed batch for single-subject consistency")
    parser.add_argument("--source-prefix", required=True, help="Match generations by source_id prefix")
    parser.add_argument("--report-id", required=True, help="Output report id")
    parser.add_argument("--write", action="store_true", help="Write rejection results into the DB")
    return parser.parse_args()


def _append_note(notes: str | None, suffix: str) -> str:
    existing = (notes or "").strip()
    if not existing:
        return suffix
    if suffix in existing:
        return existing
    return f"{existing} | {suffix}"


def main() -> None:
    args = parse_args()
    QUEUE_RUNS_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, source_id, image_path, publish_approved, notes
        FROM generations
        WHERE status = 'completed'
          AND image_path IS NOT NULL
          AND source_id LIKE ?
        ORDER BY created_at
        """,
        (f"{args.source_prefix}%",),
    ).fetchall()

    results: list[dict[str, object]] = []
    rejected = 0
    for row in rows:
        image_path = Path(settings.DATA_DIR) / str(row["image_path"])
        face_boxes = detect_faces(image_path.resolve())
        face_count = len(face_boxes)
        decision = "pass" if face_count == 1 else "reject_multi_face"
        if decision != "pass":
            rejected += 1
        results.append(
            {
                "generation_id": row["id"],
                "source_id": row["source_id"],
                "image_path": str(row["image_path"]),
                "face_count": face_count,
                "face_boxes": json.dumps(face_boxes, ensure_ascii=False),
                "decision": decision,
            }
        )
        if args.write and decision != "pass":
            conn.execute(
                """
                UPDATE generations
                SET publish_approved = 2,
                    notes = ?
                WHERE id = ?
                """,
                (
                    _append_note(
                        row["notes"],
                        f"single_subject_qc:reject(face_count={face_count})",
                    ),
                    row["id"],
                ),
            )

    if args.write:
        conn.commit()
    conn.close()

    csv_path = QUEUE_RUNS_DIR / f"{args.report_id}.csv"
    json_path = QUEUE_RUNS_DIR / f"{args.report_id}.json"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "generation_id",
                "source_id",
                "image_path",
                "face_count",
                "face_boxes",
                "decision",
            ],
        )
        writer.writeheader()
        writer.writerows(results)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "source_prefix": args.source_prefix,
                "write": args.write,
                "row_count": len(results),
                "rejected_count": rejected,
                "rows": results,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    print(
        json.dumps(
            {
                "source_prefix": args.source_prefix,
                "write": args.write,
                "row_count": len(results),
                "rejected_count": rejected,
                "csv_path": str(csv_path),
                "json_path": str(json_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

