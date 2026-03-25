#!/usr/bin/env python3
"""Queue 20-shot identity packs for all core and reserve HollowForge characters."""

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

SHOT_TEMPLATES: list[dict[str, str]] = [
    {
        "label": "shot_01_front_studio_portrait",
        "kind": "anchor_safe",
        "prompt": (
            "clean front portrait, direct eye contact, simple backdrop separation, "
            "signature hair and facial structure fully visible, polished editorial still"
        ),
    },
    {
        "label": "shot_02_three_quarter_window",
        "kind": "anchor_safe",
        "prompt": (
            "three-quarter portrait by a window, soft daylight, clean silhouette, "
            "face unobstructed, calm identity-first framing"
        ),
    },
    {
        "label": "shot_03_full_body_standing",
        "kind": "anchor_safe",
        "prompt": (
            "full-body standing shot, balanced posture, minimal environment clutter, "
            "wardrobe shape clearly readable, identity-preserving composition"
        ),
    },
    {
        "label": "shot_04_seated_medium_portrait",
        "kind": "anchor_safe",
        "prompt": (
            "medium seated portrait, one leg crossed or relaxed, clear facial readability, "
            "subtle lifestyle intimacy without heavy motion blur or distortion"
        ),
    },
    {
        "label": "shot_05_corridor_walk",
        "kind": "anchor_safe",
        "prompt": (
            "controlled corridor walk, refined body language, outfit lines clearly visible, "
            "cinematic perspective without hiding the face"
        ),
    },
    {
        "label": "shot_06_balcony_anchor",
        "kind": "anchor_safe",
        "prompt": (
            "balcony or terrace anchor shot, one hand on the rail, skyline or daylight depth, "
            "strong character silhouette and direct face readability"
        ),
    },
    {
        "label": "shot_07_cafe_table",
        "kind": "lifestyle",
        "prompt": (
            "weekday cafe table moment, drink and notebook or phone nearby, polished everyday charm, "
            "high-response lifestyle beauty"
        ),
    },
    {
        "label": "shot_08_bookstore_browse",
        "kind": "lifestyle",
        "prompt": (
            "bookstore or magazine-shelf browse, half-turn glance, casual refined styling, "
            "smart and attractive city-life energy"
        ),
    },
    {
        "label": "shot_09_flower_market",
        "kind": "lifestyle",
        "prompt": (
            "flower market or weekend stall stroll, bouquet or tote in one arm, natural daylight, "
            "romantic but grounded lifestyle desirability"
        ),
    },
    {
        "label": "shot_10_home_desk",
        "kind": "lifestyle",
        "prompt": (
            "home office or desk setup, seated with composed posture, polished domestic atmosphere, "
            "confident everyday sophistication"
        ),
    },
    {
        "label": "shot_11_kitchen_morning",
        "kind": "lifestyle",
        "prompt": (
            "morning kitchen moment, coffee or glass in hand, clean apartment lighting, "
            "quiet-luxury or polished daily routine mood"
        ),
    },
    {
        "label": "shot_12_mirror_skincare",
        "kind": "lifestyle",
        "prompt": (
            "mirror skincare or vanity routine, soft reflections, intimate but fully clothed, "
            "signature face and hair still clearly readable"
        ),
    },
    {
        "label": "shot_13_gallery_evening",
        "kind": "lifestyle",
        "prompt": (
            "gallery or exhibition evening, poised stance near a lit wall, premium cultural-social energy, "
            "elegant conversation-starting presence"
        ),
    },
    {
        "label": "shot_14_lounge_corner",
        "kind": "lifestyle",
        "prompt": (
            "late lounge corner, seated sideways on a sofa or booth edge, warm lamp light, "
            "tasteful after-dark allure with mature composure"
        ),
    },
    {
        "label": "shot_15_rooftop_afterwork",
        "kind": "lifestyle",
        "prompt": (
            "after-work rooftop pause, skyline bokeh, one hand on glass or railing, "
            "urban confidence and social magnetism"
        ),
    },
    {
        "label": "shot_16_weekend_street",
        "kind": "lifestyle",
        "prompt": (
            "weekend city street walk, tote or light outerwear, natural motion in hair and fabric, "
            "stylish public-facing lifestyle beauty"
        ),
    },
    {
        "label": "shot_17_doorway_departure",
        "kind": "lifestyle",
        "prompt": (
            "apartment or hotel doorway departure, hand on bag or coat lapel, confident glance back, "
            "signature silhouette and attitude emphasized"
        ),
    },
    {
        "label": "shot_18_soft_loungewear_window",
        "kind": "lifestyle",
        "prompt": (
            "soft knit or lounge set by a window, relaxed posture, warm natural light, "
            "platform-friendly desirability with strong identity lock"
        ),
    },
    {
        "label": "shot_19_outerwear_street",
        "kind": "lifestyle",
        "prompt": (
            "tailored outerwear street look, boots or heels, composed stride, premium editorial realism, "
            "clean full-body readability"
        ),
    },
    {
        "label": "shot_20_evening_hero",
        "kind": "hero",
        "prompt": (
            "evening hero still, strongest signature styling for the character, polished light contrast, "
            "thumbnail-friendly face readability, premium final-frame impact"
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
            c.canonical_prompt_anchor,
            c.visual_signature,
            c.wardrobe_anchors,
            c.preferred_scene_tags,
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
        WHERE c.status IN ('core', 'reserve')
          AND v.purpose = 'canonical_still'
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
        default="hf_character_identity_pack_20260321_v1",
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

    seed_base = 32130000
    batch_tags = [
        args.batch_id,
        "character_registry",
        "identity_pack",
        "canonical_still",
        "favorite_informed",
        "non_graphic_adult",
    ]

    for character_index, row in enumerate(rows, start=1):
        wardrobe_anchors = json.loads(row["wardrobe_anchors"] or "[]")
        preferred_scene_tags = json.loads(row["preferred_scene_tags"] or "[]")
        anti_drift_rules = json.loads(row["anti_drift_rules"] or "[]")
        loras = json.loads(row["loras"] or "[]")
        prompt_prefix = (row["prompt_prefix"] or "").strip()
        prompt_suffix_guidance = (row["prompt_suffix_guidance"] or "").strip()

        for shot_index, shot in enumerate(SHOT_TEMPLATES, start=1):
            seed = seed_base + (character_index * 100) + shot_index
            prompt_parts = [
                prompt_prefix
                or (
                    "masterpiece, best quality, original character, adult woman, solo, "
                    "identity-first character still, fully clothed, tasteful adult allure, "
                    "strong eye contact, luminous skin, cinematic fashion photography"
                ),
                row["canonical_prompt_anchor"],
                row["visual_signature"],
                f"wardrobe anchors: {', '.join(wardrobe_anchors[:3])}",
                f"scene tags: {', '.join(preferred_scene_tags[:3])}",
                shot["prompt"],
            ]
            if prompt_suffix_guidance:
                prompt_parts.append(prompt_suffix_guidance)
            if anti_drift_rules:
                prompt_parts.append("anti-drift: " + ", ".join(anti_drift_rules))
            prompt = ", ".join(part for part in prompt_parts if part)
            source_id = f"{args.batch_id}:{row['slug']}:{shot['label']}"
            payload = {
                "prompt": prompt,
                "negative_prompt": row["negative_prompt"] or DEFAULT_NEGATIVE_PROMPT,
                "checkpoint": row["checkpoint"],
                "workflow_lane": row["workflow_lane"] or "sdxl_illustrious",
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
                + [
                    row["status"],
                    row["slug"],
                    shot["label"],
                    shot["kind"],
                ],
                "notes": (
                    f"{args.batch_id} | {row['name']} | "
                    f"{shot['label']} | canonical identity pack"
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
                            "shot_label": shot["label"],
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
                    "shot_label": shot["label"],
                    "shot_kind": shot["kind"],
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
                    "negative_prompt": row["negative_prompt"] or DEFAULT_NEGATIVE_PROMPT,
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
