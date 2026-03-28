"""Story Planner catalog loader for canon assets."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import (
    StoryPlannerCatalog,
    StoryPlannerCharacterCatalogEntry,
    StoryPlannerLocationCatalogEntry,
    StoryPlannerPolicyPackCatalogEntry,
)


_ASSET_DIR = Path(__file__).resolve().parent.parent / "story_planner_assets"


def _load_catalog_entries(filename: str, model_cls: type) -> list:
    payload = json.loads((_ASSET_DIR / filename).read_text(encoding="utf-8"))
    return [model_cls.model_validate(item) for item in payload]


def load_story_planner_catalog() -> StoryPlannerCatalog:
    return StoryPlannerCatalog(
        characters=_load_catalog_entries(
            "characters.json",
            StoryPlannerCharacterCatalogEntry,
        ),
        locations=_load_catalog_entries(
            "locations.json",
            StoryPlannerLocationCatalogEntry,
        ),
        policy_packs=_load_catalog_entries(
            "policy_packs.json",
            StoryPlannerPolicyPackCatalogEntry,
        ),
    )
