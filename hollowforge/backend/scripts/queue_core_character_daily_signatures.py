#!/usr/bin/env python3
"""Queue 3 everyday signature images for each core HollowForge character."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

import requests


ROOT_DIR = Path(__file__).resolve().parents[2]
DB_PATH = ROOT_DIR / "data" / "hollowforge.db"
QUEUE_RUNS_DIR = ROOT_DIR / "docs" / "queue_runs"
DEFAULT_API_BASE = "http://127.0.0.1:8000"


def _load_core_character_rows() -> list[dict[str, Any]]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        """
        SELECT
            c.id AS character_id,
            c.slug,
            c.name,
            c.signature_daily_scene_briefs,
            c.canonical_prompt_anchor,
            c.visual_signature,
            c.wardrobe_anchors,
            c.anti_drift_rules,
            v.checkpoint,
            v.workflow_lane,
            v.loras,
            v.steps,
            v.cfg,
            v.sampler,
            v.scheduler,
            v.clip_skip,
            v.width,
            v.height,
            v.negative_prompt,
            v.prompt_prefix,
            v.prompt_suffix_guidance
        FROM characters c
        JOIN character_versions v
          ON v.character_id = c.id
        WHERE c.status = 'core'
          AND v.purpose = 'still_default'
        ORDER BY c.tier ASC, c.name ASC
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    con.close()
    return rows


def _queue_generation(
    session: requests.Session,
    api_base: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = session.post(
        f"{api_base}/api/v1/generations",
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help="Base URL for HollowForge backend",
    )
    parser.add_argument(
        "--batch-id",
        default="hf_core_character_daily_signatures_20260320_v1",
        help="Batch identifier for tags/notes/output files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build manifest without queueing generations",
    )
    args = parser.parse_args()

    QUEUE_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    rows = _load_core_character_rows()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    seed_base = 32020000
    batch_tags = [
        args.batch_id,
        "character_registry",
        "core_character_daily_signature",
        "favorite_informed",
        "non_graphic_adult",
    ]

    for character_index, row in enumerate(rows, start=1):
        scene_briefs = json.loads(row["signature_daily_scene_briefs"] or "[]")
        wardrobe_anchors = json.loads(row["wardrobe_anchors"] or "[]")
        anti_drift_rules = json.loads(row["anti_drift_rules"] or "[]")
        loras = json.loads(row["loras"] or "[]")
        prompt_prefix = row["prompt_prefix"].strip()
        prompt_suffix_guidance = row["prompt_suffix_guidance"].strip()

        for scene_index, scene_brief in enumerate(scene_briefs[:3], start=1):
            seed = seed_base + (character_index * 100) + scene_index
            prompt_parts = [
                prompt_prefix,
                row["canonical_prompt_anchor"],
                row["visual_signature"],
                f"wardrobe anchors: {', '.join(wardrobe_anchors[:2])}",
                scene_brief,
            ]
            if prompt_suffix_guidance:
                prompt_parts.append(prompt_suffix_guidance)
            if anti_drift_rules:
                prompt_parts.append(
                    "anti-drift: " + ", ".join(anti_drift_rules)
                )
            prompt = ", ".join(part for part in prompt_parts if part)
            source_id = f"{args.batch_id}:{row['slug']}:scene_{scene_index:02d}"
            payload = {
                "prompt": prompt,
                "negative_prompt": row["negative_prompt"],
                "checkpoint": row["checkpoint"],
                "workflow_lane": row["workflow_lane"],
                "loras": loras,
                "seed": seed,
                "steps": row["steps"],
                "cfg": row["cfg"],
                "width": row["width"],
                "height": row["height"],
                "sampler": row["sampler"],
                "scheduler": row["scheduler"],
                "clip_skip": row["clip_skip"],
                "tags": batch_tags
                + [row["slug"], f"scene_{scene_index:02d}", "daily_signature"],
                "notes": (
                    f"{args.batch_id} | {row['name']} | daily signature {scene_index:02d}"
                ),
                "source_id": source_id,
            }

            if args.dry_run:
                generation_id = ""
                status = "dry_run"
            else:
                try:
                    queued = _queue_generation(session, args.api_base, payload)
                except Exception as exc:  # pragma: no cover - operational script
                    errors.append(
                        {
                            "character_name": row["name"],
                            "scene_index": scene_index,
                            "error": str(exc),
                        }
                    )
                    continue
                generation_id = queued["id"]
                status = queued["status"]

            results.append(
                {
                    "generation_id": generation_id,
                    "status": status,
                    "character_name": row["name"],
                    "character_slug": row["slug"],
                    "scene_index": scene_index,
                    "checkpoint": row["checkpoint"],
                    "loras": json.dumps(loras, ensure_ascii=False),
                    "seed": seed,
                    "steps": row["steps"],
                    "cfg": row["cfg"],
                    "sampler": row["sampler"],
                    "scheduler": row["scheduler"],
                    "clip_skip": row["clip_skip"],
                    "resolution": f"{row['width']}x{row['height']}",
                    "prompt": prompt,
                    "negative_prompt": row["negative_prompt"],
                    "notes": payload["notes"],
                    "source_id": source_id,
                }
            )

    csv_path = QUEUE_RUNS_DIR / f"{args.batch_id}.csv"
    json_path = QUEUE_RUNS_DIR / f"{args.batch_id}.json"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "batch_id": args.batch_id,
                "queued_count": len(results),
                "errors": errors,
                "rows": results,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )

    summary: dict[str, Any] = {
        "batch_id": args.batch_id,
        "queued_count": len(results),
        "error_count": len(errors),
        "csv_path": str(csv_path),
        "json_path": str(json_path),
    }
    if not args.dry_run:
        queue_summary = session.get(
            f"{args.api_base}/api/v1/generations/queue/summary",
            timeout=30,
        ).json()
        summary["queue_summary"] = {
            "total_running": queue_summary["total_running"],
            "total_queued": queue_summary["total_queued"],
            "total_active": queue_summary["total_active"],
            "estimated_remaining_sec": queue_summary["estimated_remaining_sec"],
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
