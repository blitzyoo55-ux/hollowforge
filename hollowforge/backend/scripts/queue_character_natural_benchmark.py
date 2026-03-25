#!/usr/bin/env python3
"""Queue a small natural-look benchmark batch for all core and reserve characters."""

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
SINGLE_SUBJECT_PROMPT = (
    "single subject only, one woman only, no companion, no bystander, "
    "no reflected duplicate, clear primary subject, subject occupies the focal plane"
)
DEFAULT_NEGATIVE_PROMPT = (
    "child, teen, underage, school uniform, text, logo, watermark, blurry, "
    "lowres, deformed, bad anatomy, extra fingers, duplicate, poorly drawn hands, "
    "plastic skin, hyper-glossy skin, doll-like eyes, over-sharpened details, "
    "exaggerated makeup, stiff pose, sticker-like subject, pasted background, mismatched perspective, "
    "flat depth, repeated background assets, duplicated props, weak contact shadows, floating limbs, "
    "two women, two people, multiple women, twins, sisters, duplicate person, mirror clone, "
    "second subject, extra subject, side-by-side composition, companion, background pedestrian, "
    "foreground person, reflected person, repeated face, double body, shared umbrella pair, "
    "explicit nudity, graphic sexual content"
)

SHOT_PROFILES: list[dict[str, str]] = [
    {
        "label": "scene_01_close_anchor",
        "kind": "natural_anchor",
        "fallback_prompt": (
            "quiet close anchor moment, relaxed shoulders, natural eye line, slight asymmetry, "
            "believable skin and hair texture, calm lived-in realism"
        ),
        "camera": "eye-level medium close shot, 50mm portrait feel, chest-up framing with a little room around the subject",
        "depth": "foreground edge from a desk, doorway, curtain, or work surface, clear single subject in the midground, readable depth behind",
        "interaction": "one hand touching a desk edge, notebook, cup, chair back, or sleeve cuff so the subject feels physically grounded",
        "background": "site-specific room or work details, varied light falloff, no blank backdrop, no mirrored second figure, no stock-photo symmetry",
        "negative_extra": "split face, split hair color, half-and-half styling, mirrored centerline, two-tone face, composite portrait",
    },
    {
        "label": "scene_02_grounded_pause",
        "kind": "daily_natural",
        "fallback_prompt": (
            "workday or domestic pause with a practical object nearby, casual calm, "
            "natural fabric folds, believable everyday atmosphere"
        ),
        "camera": "waist-up environmental shot from counter, desk, or hallway height, slightly off-center composition",
        "depth": "foreground practical object, clear subject placement, readable interior depth behind without extra figures",
        "interaction": "hand resting on an object, handle, rail, tote, or garment edge with believable weight and contact",
        "background": "realistic interior variation with practical clutter, non-repeating surfaces, and no secondary person cues",
        "negative_extra": "reflection double, duplicate reflection, second face in reflection",
    },
    {
        "label": "scene_03_public_half_turn",
        "kind": "daily_natural",
        "fallback_prompt": (
            "public everyday half-turn glance, unforced posture, understated charm, "
            "no glossy posing or paired framing"
        ),
        "camera": "medium environmental shot from aisle or corridor height, slight three-quarter angle with a single clear subject",
        "depth": "one shelf edge, fixture edge, or product stack in the near foreground, subject in the midground, long public-space depth behind",
        "interaction": "one hand on a product, book, rail, tote, or phone so the body reads as occupied in the environment",
        "background": "public-space details should vary by shelf density, signage, and light pockets instead of template rows or paired compositions",
        "negative_extra": "shopping pair, two shoppers, pair portrait, shared browsing pose",
    },
    {
        "label": "scene_04_settled_interior",
        "kind": "daily_natural",
        "fallback_prompt": (
            "settled interior moment, relaxed hands and posture, casual knitwear or homewear, "
            "soft ambient light, personality-first framing"
        ),
        "camera": "medium-wide interior shot with enough space to read body posture and surrounding furniture or fixtures",
        "depth": "foreground textile, counter edge, or chair arm, subject settled into the midground, background lamp or shelf giving spatial depth",
        "interaction": "clear body weight on a seat, counter, sink, or doorway edge with a naturally held object and believable contact",
        "background": "lived-in interior details, layered textiles or objects, slight asymmetry, and varied furniture shapes rather than showroom neatness",
        "negative_extra": "shared sofa, paired seating, second person in room, second woman indoors",
    },
    {
        "label": "scene_05_exterior_transition",
        "kind": "daily_natural",
        "fallback_prompt": (
            "exterior transition moment, light outerwear, realistic city or neighborhood atmosphere, slight wind in hair, "
            "observational mood, natural stride"
        ),
        "camera": "50mm waist-up or three-quarter exterior shot, natural eye-level angle, one clear heroine occupying most of the frame",
        "depth": "foreground pavement, curb, or object detail, grounded contact shadow under one subject, layered exterior depth behind",
        "interaction": "footfall, coat movement, tote, notebook, phone, or rail contact should visibly connect the subject to the scene",
        "background": "street or rooftop assets must vary organically, with irregular geometry and weather detail instead of repeated facades or extra pedestrians",
        "negative_extra": "fashion duo, two-shot fashion pose, shared umbrella pair, side-by-side women, street-style pair",
    },
    {
        "label": "scene_06_evening_rest",
        "kind": "natural_anchor",
        "fallback_prompt": (
            "quiet evening rest, one hand on a rail, cup, shelf, or tote, gentle end-of-day light, "
            "calm lived-in realism, beautiful but not over-staged"
        ),
        "camera": "medium-wide side angle, slightly pulled back so the environment breathes around one clear subject",
        "depth": "railing, desk edge, or doorway frame in the near plane, subject in the midground, layered distance behind",
        "interaction": "clear hand contact with a rail, cup, chair arm, shelf, or window ledge so the figure does not look pasted in",
        "background": "end-of-day background should feel site-specific with varied building shapes, light spill, and distance haze, without duplicated silhouettes",
        "negative_extra": "paired balcony, second silhouette, shared evening pose",
    },
]


def _merge_negative_prompt(base_prompt: str | None) -> str:
    merged_parts: list[str] = []
    for chunk in (base_prompt or "", DEFAULT_NEGATIVE_PROMPT):
        for item in chunk.split(","):
            cleaned = item.strip()
            if cleaned and cleaned not in merged_parts:
                merged_parts.append(cleaned)
    return ", ".join(merged_parts)


def _normalize_scene_brief(scene_brief: str) -> str:
    normalized = " ".join(scene_brief.split())
    replacements = {
        "elevator mirror hair tuck": "elevator wait with a hand brushing hair back",
        "mirror and notes": "notes beside a prep counter",
        "mirror": "reflective wall panel",
    }
    lower_text = normalized.lower()
    for source, target in replacements.items():
        if source in lower_text:
            start = lower_text.index(source)
            end = start + len(source)
            normalized = normalized[:start] + target + normalized[end:]
            lower_text = normalized.lower()
    return normalized


def _load_shot_override(raw_value: str | None, shot_label: str) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    shot_override = parsed.get(shot_label, {})
    return shot_override if isinstance(shot_override, dict) else {}


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
            c.profession,
            c.background,
            c.personality,
            c.canonical_prompt_anchor,
            c.visual_signature,
            c.wardrobe_anchors,
            c.preferred_scene_tags,
            c.natural_scene_briefs,
            c.natural_shot_overrides,
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
          AND v.purpose = 'canonical_natural'
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
        default="hf_character_natural_benchmark_20260322_v2",
        help="Batch identifier for tags/notes/output files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build manifest without queueing generations",
    )
    parser.add_argument(
        "--character-slug",
        help="Optional character slug filter for targeted reruns",
    )
    parser.add_argument(
        "--shot-label",
        action="append",
        help="Optional shot label filter; can be provided multiple times",
    )
    args = parser.parse_args()

    QUEUE_RUNS_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    rows = _load_character_rows()
    if args.character_slug:
        rows = [row for row in rows if row["slug"] == args.character_slug]
    if not rows:
        raise SystemExit(f"No characters found for filter: {args.character_slug!r}")
    results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    seed_base = 32150000
    batch_tags = [
        args.batch_id,
        "character_registry",
        "natural_benchmark",
        "canonical_natural",
        "favorite_informed",
        "fully_clothed",
    ]

    for character_index, row in enumerate(rows, start=1):
        wardrobe_anchors = json.loads(row["wardrobe_anchors"] or "[]")
        preferred_scene_tags = json.loads(row["preferred_scene_tags"] or "[]")
        natural_scene_briefs = json.loads(row["natural_scene_briefs"] or "[]")
        anti_drift_rules = json.loads(row["anti_drift_rules"] or "[]")
        loras = json.loads(row["loras"] or "[]")
        prompt_prefix = (row["prompt_prefix"] or "").strip()
        prompt_suffix_guidance = (row["prompt_suffix_guidance"] or "").strip()

        for shot_index, shot in enumerate(SHOT_PROFILES, start=1):
            if args.shot_label and shot["label"] not in args.shot_label:
                continue
            shot_override = _load_shot_override(row.get("natural_shot_overrides"), shot["label"])
            seed = seed_base + (character_index * 100) + shot_index
            scene_brief = _normalize_scene_brief(
                shot_override.get("scene_brief")
                or (
                    natural_scene_briefs[shot_index - 1]
                    if len(natural_scene_briefs) >= shot_index
                    else shot["fallback_prompt"]
                )
            )
            wardrobe_anchor = (
                wardrobe_anchors[(shot_index - 1) % len(wardrobe_anchors)]
                if wardrobe_anchors
                else ""
            )
            scene_hint = (
                preferred_scene_tags[(shot_index - 1) % len(preferred_scene_tags)]
                if preferred_scene_tags
                else ""
            )
            effective_prompt_prefix = (shot_override.get("prompt_prefix") or prompt_prefix).strip()
            effective_prompt_suffix_guidance = (
                shot_override.get("prompt_suffix_guidance") or prompt_suffix_guidance
            ).strip()
            effective_checkpoint = shot_override.get("checkpoint") or row["checkpoint"]
            effective_loras = shot_override.get("loras", loras)
            effective_steps = shot_override.get("steps", row["steps"])
            effective_cfg = shot_override.get("cfg", row["cfg"])
            effective_sampler = shot_override.get("sampler", row["sampler"])
            effective_scheduler = shot_override.get("scheduler", row["scheduler"])
            effective_clip_skip = shot_override.get("clip_skip", row["clip_skip"])
            effective_width = shot_override.get("width", row["width"])
            effective_height = shot_override.get("height", row["height"])
            effective_camera = shot_override.get("camera") or shot["camera"]
            effective_depth = shot_override.get("depth") or shot["depth"]
            effective_interaction = shot_override.get("interaction") or shot["interaction"]
            effective_background = shot_override.get("background") or shot["background"]
            prompt_parts = [
                effective_prompt_prefix
                or (
                    "masterpiece, best quality, original character, adult woman, solo, "
                    "fully clothed, natural beauty illustration, relaxed expression, subtle skin texture, "
                    "soft ambient light, delicate linework, painterly shading"
                ),
                SINGLE_SUBJECT_PROMPT,
                row["canonical_prompt_anchor"],
                row["visual_signature"],
                f"profession anchor: {row['profession'] or row['background']}",
                f"personality cues: {row['personality']}",
                f"wardrobe anchor: {wardrobe_anchor}" if wardrobe_anchor else "",
                f"scene mood hint: {scene_hint}" if scene_hint else "",
                scene_brief,
                f"camera profile: {effective_camera}",
                f"depth staging: {effective_depth}",
                f"environment interaction: {effective_interaction}",
                f"background behavior: {effective_background}",
            ]
            if effective_prompt_suffix_guidance:
                prompt_parts.append(effective_prompt_suffix_guidance)
            if anti_drift_rules:
                prompt_parts.append("anti-drift: " + ", ".join(anti_drift_rules))
            prompt = ", ".join(part for part in prompt_parts if part)
            source_id = f"{args.batch_id}:{row['slug']}:{shot['label']}"
            payload = {
                "prompt": prompt,
                "negative_prompt": _merge_negative_prompt(
                    ", ".join(
                        item
                        for item in [
                            row["negative_prompt"] or "",
                            shot.get("negative_extra", ""),
                            shot_override.get("negative_prompt_extra", ""),
                        ]
                        if item
                    )
                ),
                "checkpoint": effective_checkpoint,
                "workflow_lane": row["workflow_lane"] or "sdxl_illustrious",
                "loras": effective_loras,
                "seed": seed,
                "steps": effective_steps,
                "cfg": effective_cfg,
                "width": effective_width,
                "height": effective_height,
                "sampler": effective_sampler,
                "scheduler": effective_scheduler,
                "clip_skip": effective_clip_skip,
                "tags": batch_tags + [row["status"], row["slug"], shot["label"], shot["kind"]],
                "notes": (
                    f"{args.batch_id} | {row['name']} | "
                    f"{shot['label']} | canonical natural benchmark"
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
                    "checkpoint": effective_checkpoint,
                    "loras": json.dumps(effective_loras, ensure_ascii=False),
                    "seed": seed,
                    "steps": effective_steps,
                    "cfg": effective_cfg,
                    "sampler": effective_sampler,
                    "scheduler": effective_scheduler,
                    "clip_skip": effective_clip_skip,
                    "resolution": f"{effective_width}x{effective_height}",
                    "prompt": prompt,
                    "negative_prompt": _merge_negative_prompt(
                        ", ".join(
                            item
                            for item in [
                                row["negative_prompt"] or "",
                                shot.get("negative_extra", ""),
                                shot_override.get("negative_prompt_extra", ""),
                            ]
                            if item
                        )
                    ),
                    "notes": payload["notes"],
                    "source_id": source_id,
                }
            )

    csv_path = QUEUE_RUNS_DIR / f"{args.batch_id}.csv"
    json_path = QUEUE_RUNS_DIR / f"{args.batch_id}.json"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(results[0].keys()) if results else [
            "generation_id",
            "status",
            "character_name",
            "character_slug",
            "character_status",
            "character_tier",
            "shot_label",
            "shot_kind",
            "checkpoint",
            "loras",
            "seed",
            "steps",
            "cfg",
            "sampler",
            "scheduler",
            "clip_skip",
            "resolution",
            "prompt",
            "negative_prompt",
            "notes",
            "source_id",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if results:
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
