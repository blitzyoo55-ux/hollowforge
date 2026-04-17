from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT_DIR / "data" / "quality" / "favorite_recipe_catalog.json"
REPORT_PATH = ROOT_DIR / "docs" / "quality" / "favorite_recipe_report.json"
SHARED_DB_PATH = ROOT_DIR.parents[2] / "hollowforge" / "data" / "hollowforge.db"

ROOM_SAFE_PREFERENCE = (
    "akiumLumenILLBase_baseV2.safetensors",
    "hassakuXLIllustrious_v34.safetensors",
    "waiIllustriousSDXL_v140.safetensors",
    "waiIllustriousSDXL_v160.safetensors",
    "prefectIllustriousXL_v70.safetensors",
)

LIFESTYLE_SAFE_PREFERENCE = (
    "prefectIllustriousXL_v70.safetensors",
    "waiIllustriousSDXL_v160.safetensors",
    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
)

CLOSEUP_ENHANCER_PREFERENCE = (
    "prefectIllustriousXL_v70.safetensors",
    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
    "illustrij_v20.safetensors",
)


def _query_rows(conn: sqlite3.Connection, sql: str) -> list[dict[str, object]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql).fetchall()]


def _pick_checkpoint(
    candidates: list[dict[str, object]],
    preference_order: tuple[str, ...],
) -> str:
    candidate_index = {
        str(item.get("checkpoint") or ""): item for item in candidates if item.get("checkpoint")
    }
    for checkpoint in preference_order:
        if checkpoint in candidate_index:
            return checkpoint
    if not candidates:
        raise RuntimeError("No favorite checkpoint candidates found")
    return str(candidates[0]["checkpoint"])


def _pick_closeup_combo(
    candidates: list[dict[str, object]],
) -> tuple[str, list[dict[str, object]]]:
    for checkpoint in CLOSEUP_ENHANCER_PREFERENCE:
        for candidate in candidates:
            if str(candidate.get("checkpoint") or "") != checkpoint:
                continue
            raw_loras = str(candidate.get("loras") or "[]")
            return checkpoint, json.loads(raw_loras)
    if not candidates:
        raise RuntimeError("No enhancer combo favorite candidates found")
    fallback = candidates[0]
    return str(fallback["checkpoint"]), json.loads(str(fallback.get("loras") or "[]"))


def _safe_no_lora_candidates(conn: sqlite3.Connection) -> list[dict[str, object]]:
    return _query_rows(
        conn,
        """
        SELECT checkpoint, COUNT(*) AS count
        FROM generations
        WHERE is_favorite = 1
          AND lower(prompt) LIKE '%adult woman%'
          AND lower(prompt) LIKE '%fully clothed%'
          AND loras = '[]'
        GROUP BY checkpoint
        ORDER BY count DESC, checkpoint ASC
        """,
    )


def _enhancer_combo_candidates(conn: sqlite3.Connection) -> list[dict[str, object]]:
    return _query_rows(
        conn,
        """
        SELECT checkpoint, loras, COUNT(*) AS count
        FROM generations
        WHERE is_favorite = 1
          AND lower(loras) LIKE '%detailedeyes%'
          AND lower(loras) LIKE '%face_enhancer_illustrious%'
        GROUP BY checkpoint, loras
        ORDER BY count DESC, checkpoint ASC
        """,
    )


def _favorite_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM generations WHERE is_favorite = 1"
    ).fetchone()
    return int(row[0]) if row else 0


def build_catalog_payload(
    *,
    room_checkpoint: str,
    lifestyle_checkpoint: str,
    closeup_checkpoint: str,
    closeup_loras: list[dict[str, object]],
) -> dict[str, object]:
    enhancer_loras = closeup_loras[:2]
    return {
        "version": "2026-04-11",
        "recipes": [
            {
                "recipe_id": "favorite_room_safe_v1",
                "family": "room_safe",
                "apply_execution_override": True,
                "checkpoint": room_checkpoint,
                "loras": [],
                "steps": 28,
                "cfg": 5.1,
                "sampler": "euler_a",
                "prompt_fragments": [
                    "spacious readable room layout",
                    "single adult lead secondary to environment",
                ],
                "negative_fragments": [
                    "empty background",
                    "minimal room detail",
                    "subject filling frame",
                    "single-subject glamour poster",
                    "beauty key visual",
                    "camera frame",
                    "viewfinder",
                    "screenshot border",
                    "subtitle overlay",
                ],
            },
            {
                "recipe_id": "favorite_lifestyle_safe_v1",
                "family": "lifestyle_safe",
                "apply_execution_override": False,
                "checkpoint": lifestyle_checkpoint,
                "loras": enhancer_loras,
                "steps": 30,
                "cfg": 5.4,
                "sampler": "euler_a",
                "prompt_fragments": [
                    "natural body pose",
                    "clear hand acting",
                ],
                "negative_fragments": [
                    "single-subject glamour poster",
                    "beauty key visual",
                    "waxy skin",
                    "dead eyes",
                    "camera frame",
                    "subtitle overlay",
                ],
            },
            {
                "recipe_id": "favorite_comic_close_safe_v1",
                "family": "comic_close_safe",
                "apply_execution_override": False,
                "checkpoint": closeup_checkpoint,
                "loras": enhancer_loras,
                "steps": 30,
                "cfg": 5.4,
                "sampler": "euler_a",
                "prompt_fragments": [
                    "adult facial clarity",
                    "alive eyes",
                ],
                "negative_fragments": [
                    "plastic skin",
                    "waxy face",
                    "dead eyes",
                    "camera frame",
                    "subtitle overlay",
                ],
            },
        ],
    }


def main() -> None:
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(SHARED_DB_PATH) as conn:
        safe_candidates = _safe_no_lora_candidates(conn)
        enhancer_candidates = _enhancer_combo_candidates(conn)
        favorite_count = _favorite_count(conn)

    room_checkpoint = _pick_checkpoint(safe_candidates, ROOM_SAFE_PREFERENCE)
    lifestyle_checkpoint = _pick_checkpoint(
        safe_candidates, LIFESTYLE_SAFE_PREFERENCE
    )
    closeup_checkpoint, closeup_loras = _pick_closeup_combo(enhancer_candidates)

    catalog = build_catalog_payload(
        room_checkpoint=room_checkpoint,
        lifestyle_checkpoint=lifestyle_checkpoint,
        closeup_checkpoint=closeup_checkpoint,
        closeup_loras=closeup_loras,
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_db": str(SHARED_DB_PATH),
        "favorite_count": favorite_count,
        "safe_no_lora_candidates": safe_candidates,
        "enhancer_combo_candidates": enhancer_candidates,
        "selected_recipes": {
            recipe["family"]: {
                "recipe_id": recipe["recipe_id"],
                "checkpoint": recipe["checkpoint"],
                "loras": [item.get("filename") for item in recipe["loras"]],
            }
            for recipe in catalog["recipes"]
        },
    }

    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
