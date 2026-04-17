"""Static favorite-informed quality recipe catalog for comic rendering."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


_CATALOG_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "quality" / "favorite_recipe_catalog.json"
)


class FavoriteQualityRecipeEntry(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    recipe_id: str = Field(min_length=1, max_length=120)
    family: str = Field(min_length=1, max_length=120)
    apply_execution_override: bool = False
    checkpoint: str = Field(min_length=1, max_length=255)
    loras: tuple[dict[str, object], ...] = Field(default_factory=tuple)
    steps: int = Field(ge=1, le=100)
    cfg: float = Field(gt=0.0, le=30.0)
    sampler: str = Field(min_length=1, max_length=120)
    prompt_fragments: tuple[str, ...] = Field(default_factory=tuple)
    negative_fragments: tuple[str, ...] = Field(default_factory=tuple)


class FavoriteQualityRecipeCatalog(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    version: str = Field(min_length=1, max_length=120)
    recipes: tuple[FavoriteQualityRecipeEntry, ...] = Field(default_factory=tuple)


@lru_cache(maxsize=1)
def load_favorite_quality_recipe_catalog() -> FavoriteQualityRecipeCatalog:
    if not _CATALOG_PATH.exists():
        raise ValueError(
            "Favorite quality recipe catalog is missing: "
            f"{_CATALOG_PATH}"
        )

    payload = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return FavoriteQualityRecipeCatalog.model_validate(payload)


def get_favorite_quality_recipe(
    *,
    recipe_family: str,
) -> FavoriteQualityRecipeEntry | None:
    family = recipe_family.strip()
    if not family:
        return None

    catalog = load_favorite_quality_recipe_catalog()
    for recipe in catalog.recipes:
        if recipe.family == family:
            return recipe
    return None
