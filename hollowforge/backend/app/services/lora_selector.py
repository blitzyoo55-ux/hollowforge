"""Smart LoRA selection engine based on mood keywords."""

from __future__ import annotations

import json
from typing import Any

import aiosqlite

from app.models import LoraInput
from app.services.model_compatibility import is_checkpoint_compatible

# Category slot limits
CATEGORY_SLOTS: dict[str, int] = {
    "style": 1,
    "eyes": 1,
    "material": 1,
    "fetish": 2,
}

MAX_TOTAL_STRENGTH = 2.4

APPLICATION_ORDER = ["style", "eyes", "material", "fetish"]


def _parse_json(val: str | None, default: Any = None) -> Any:
    if val is None:
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


async def select_by_moods(
    db: aiosqlite.Connection,
    moods: list[str],
    checkpoint: str | None = None,
    available_filenames: set[str] | None = None,
) -> tuple[list[LoraInput], str]:
    """Select LoRAs based on mood keywords.

    1. Look up mood_mappings for each keyword
    2. Collect lora_ids, resolve to lora_profiles
    3. Fill category slots respecting limits
    4. Cap total strength at MAX_TOTAL_STRENGTH
    5. Order by APPLICATION_ORDER
    6. Collect prompt_additions

    Returns (selected_loras, combined_prompt_additions).
    """
    collected_lora_ids: list[str] = []
    prompt_parts: list[str] = []

    # 1. Gather lora_ids and prompt_additions from mood_mappings
    for mood in moods:
        cursor = await db.execute(
            "SELECT lora_ids, prompt_additions FROM mood_mappings WHERE mood_keyword = ?",
            (mood.lower(),),
        )
        row = await cursor.fetchone()
        if row is None:
            continue
        ids = _parse_json(row["lora_ids"], [])
        collected_lora_ids.extend(ids)
        if row.get("prompt_additions"):
            prompt_parts.append(row["prompt_additions"])

    if not collected_lora_ids:
        return [], ""

    # 2. Deduplicate while preserving order
    seen: set[str] = set()
    unique_ids: list[str] = []
    for lid in collected_lora_ids:
        if lid not in seen:
            seen.add(lid)
            unique_ids.append(lid)

    # 3. Resolve lora_profiles
    placeholders = ",".join("?" for _ in unique_ids)
    cursor = await db.execute(
        f"SELECT * FROM lora_profiles WHERE id IN ({placeholders})",
        unique_ids,
    )
    rows = await cursor.fetchall()
    profile_map: dict[str, dict[str, Any]] = {r["id"]: r for r in rows}

    # Filter by availability + checkpoint compatibility if provided
    for pid, prof in list(profile_map.items()):
        if available_filenames and prof["filename"] not in available_filenames:
            del profile_map[pid]
            continue
        if checkpoint and not is_checkpoint_compatible(
            prof.get("compatible_checkpoints"), checkpoint
        ):
            del profile_map[pid]

    # 4. Fill category slots
    category_counts: dict[str, int] = {}
    selected: list[LoraInput] = []

    for lid in unique_ids:
        prof = profile_map.get(lid)
        if prof is None:
            continue
        cat = prof["category"]
        max_slots = CATEGORY_SLOTS.get(cat, 1)
        current = category_counts.get(cat, 0)
        if current >= max_slots:
            continue
        category_counts[cat] = current + 1
        selected.append(
            LoraInput(
                filename=prof["filename"],
                strength=prof["default_strength"],
                category=cat,
            )
        )

    # 5. Cap total strength
    total = sum(l.strength for l in selected)
    if total > MAX_TOTAL_STRENGTH and total > 0:
        ratio = MAX_TOTAL_STRENGTH / total
        selected = [
            LoraInput(
                filename=l.filename,
                strength=round(l.strength * ratio, 3),
                category=l.category,
            )
            for l in selected
        ]

    # 6. Sort by APPLICATION_ORDER
    order_map = {cat: i for i, cat in enumerate(APPLICATION_ORDER)}
    selected.sort(key=lambda l: order_map.get(l.category or "", 99))

    prompt_additions = ", ".join(prompt_parts)
    return selected, prompt_additions
