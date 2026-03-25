#!/usr/bin/env python3
"""Queue one signature image per shared combo for every core/reserve character."""

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
DEFAULT_NEGATIVE_PROMPT = (
    "child, teen, underage, school uniform, text, logo, watermark, blurry, "
    "lowres, deformed, bad anatomy, extra fingers, duplicate, poorly drawn hands, "
    "explicit nudity, graphic sexual content"
)

COMBOS: list[dict[str, Any]] = [
    {
        "label": "combo_a",
        "display_name": "Golden Still Base",
        "checkpoint": "prefectIllustriousXL_v70.safetensors",
        "loras": [
            {
                "filename": "DetailedEyes_V3.safetensors",
                "strength": 0.45,
                "category": "eyes",
            },
            {
                "filename": "Face_Enhancer_Illustrious.safetensors",
                "strength": 0.36,
                "category": "style",
            },
        ],
        "steps": 31,
        "cfg": 5.35,
        "combo_guidance": (
            "Favor balanced face readability, signature silhouette clarity, "
            "and reliable character-lock rendering."
        ),
    },
    {
        "label": "combo_b",
        "display_name": "Golden Style Variant",
        "checkpoint": "waiIllustriousSDXL_v140.safetensors",
        "loras": [
            {
                "filename": "Seet_il5-000009.safetensors",
                "strength": 0.40,
                "category": "style",
            },
            {
                "filename": "DetailedEyes_V3.safetensors",
                "strength": 0.42,
                "category": "eyes",
            },
        ],
        "steps": 32,
        "cfg": 5.40,
        "combo_guidance": (
            "Favor elegant fabric rendering, graceful lifestyle atmosphere, "
            "and refined premium-fashion polish."
        ),
    },
    {
        "label": "combo_c",
        "display_name": "Golden High-Reaction Still",
        "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
        "loras": [
            {
                "filename": "Face_Enhancer_Illustrious.safetensors",
                "strength": 0.34,
                "category": "style",
            },
            {
                "filename": "DetailedEyes_V3.safetensors",
                "strength": 0.41,
                "category": "eyes",
            },
        ],
        "steps": 34,
        "cfg": 5.50,
        "combo_guidance": (
            "Favor high-impact thumbnail readability, polished glamour finish, "
            "and strong direct eye contact."
        ),
    },
]


def _load_character_rows() -> list[dict[str, Any]]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        """
        SELECT
            c.id AS character_id,
            c.slug,
            c.name,
            c.status,
            c.tier,
            c.signature_daily_scene_briefs,
            c.canonical_prompt_anchor,
            c.visual_signature,
            c.wardrobe_anchors,
            c.anti_drift_rules
        FROM characters c
        WHERE c.status IN ('core', 'reserve')
        ORDER BY
            CASE c.status WHEN 'core' THEN 0 WHEN 'reserve' THEN 1 ELSE 2 END,
            c.tier ASC,
            c.name ASC
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
        default="hf_character_signature_combo_matrix_20260321_v1",
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
    rows = _load_character_rows()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    seed_base = 32121000
    batch_tags = [
        args.batch_id,
        "character_registry",
        "signature_matrix",
        "favorite_informed",
        "non_graphic_adult",
    ]

    for character_index, row in enumerate(rows, start=1):
        scene_briefs = json.loads(row["signature_daily_scene_briefs"] or "[]")
        wardrobe_anchors = json.loads(row["wardrobe_anchors"] or "[]")
        anti_drift_rules = json.loads(row["anti_drift_rules"] or "[]")

        for combo_index, combo in enumerate(COMBOS, start=1):
            scene_brief = scene_briefs[combo_index - 1] if len(scene_briefs) >= combo_index else ""
            seed = seed_base + (character_index * 100) + combo_index
            prompt_parts = [
                (
                    "masterpiece, best quality, original character, adult woman, solo, "
                    "signature character portrait, high-response beauty editorial, "
                    "fully clothed, tasteful adult allure, strong eye contact, luminous skin, "
                    "cinematic fashion photography"
                ),
                row["canonical_prompt_anchor"],
                row["visual_signature"],
                f"wardrobe anchors: {', '.join(wardrobe_anchors[:2])}",
                scene_brief,
                combo["combo_guidance"],
            ]
            if anti_drift_rules:
                prompt_parts.append(
                    "anti-drift: " + ", ".join(anti_drift_rules)
                )
            prompt = ", ".join(part for part in prompt_parts if part)
            source_id = f"{args.batch_id}:{row['slug']}:{combo['label']}"
            payload = {
                "prompt": prompt,
                "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
                "checkpoint": combo["checkpoint"],
                "workflow_lane": "sdxl_illustrious",
                "loras": combo["loras"],
                "seed": seed,
                "steps": combo["steps"],
                "cfg": combo["cfg"],
                "width": 832,
                "height": 1216,
                "sampler": "euler_ancestral",
                "scheduler": "normal",
                "clip_skip": 2,
                "tags": batch_tags
                + [
                    row["status"],
                    row["slug"],
                    combo["label"],
                    "signature_image",
                ],
                "notes": (
                    f"{args.batch_id} | {row['name']} | {combo['display_name']} | "
                    f"{combo['label']}"
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
                            "combo_label": combo["label"],
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
                    "character_status": row["status"],
                    "character_tier": row["tier"],
                    "combo_label": combo["label"],
                    "combo_name": combo["display_name"],
                    "checkpoint": combo["checkpoint"],
                    "loras": json.dumps(combo["loras"], ensure_ascii=False),
                    "seed": seed,
                    "steps": combo["steps"],
                    "cfg": combo["cfg"],
                    "sampler": "euler_ancestral",
                    "scheduler": "normal",
                    "clip_skip": 2,
                    "resolution": "832x1216",
                    "prompt": prompt,
                    "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
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
                "error_count": len(errors),
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
