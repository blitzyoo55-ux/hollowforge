"""Registry for bindings between character canon and series style canon entries."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CharacterSeriesBindingEntry(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    id: str = Field(min_length=1, max_length=120)
    character_id: str = Field(min_length=1, max_length=120)
    series_style_id: str = Field(min_length=1, max_length=120)
    identity_lock_strength: str = Field(min_length=1, max_length=120)
    hair_lock_strength: str = Field(min_length=1, max_length=120)
    face_lock_strength: str = Field(min_length=1, max_length=120)
    allowed_wardrobe_family: str = Field(min_length=1, max_length=120)
    binding_negative_rules: str = Field(min_length=1, max_length=1000)
    do_not_mutate: str = Field(min_length=1, max_length=1000)
    notes: str = Field(min_length=1, max_length=1000)


_CHARACTER_SERIES_BINDING_REGISTRY: dict[str, CharacterSeriesBindingEntry] = {
    "camila_pilot_binding_v1": CharacterSeriesBindingEntry(
        id="camila_pilot_binding_v1",
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
        identity_lock_strength="strong",
        hair_lock_strength="strong",
        face_lock_strength="strong",
        allowed_wardrobe_family="simple functional everyday wardrobe",
        binding_negative_rules=(
            "No wardrobe drift, no glamour drift, no editorial styling drift."
        ),
        do_not_mutate=(
            "Do not mutate Camila identity ownership, style ownership, or checkpoint "
            "ownership through this binding."
        ),
        notes="Camila-only pilot binding for the V2 registry pilot.",
    )
}


def _validate_binding_registry_pairs() -> None:
    seen_pairs: set[tuple[str, str]] = set()
    for binding in _CHARACTER_SERIES_BINDING_REGISTRY.values():
        pair = (binding.character_id, binding.series_style_id)
        if pair in seen_pairs:
            raise RuntimeError(
                "Duplicate character-series binding pair in registry: "
                f"{binding.character_id} + {binding.series_style_id}"
            )
        seen_pairs.add(pair)


_validate_binding_registry_pairs()


def _get_binding_by_character_and_style(
    *,
    character_id: str,
    series_style_id: str,
) -> CharacterSeriesBindingEntry | None:
    for binding in _CHARACTER_SERIES_BINDING_REGISTRY.values():
        if (
            binding.character_id == character_id
            and binding.series_style_id == series_style_id
        ):
            return binding
    return None


def get_character_series_binding(binding_id: str) -> CharacterSeriesBindingEntry:
    binding = _CHARACTER_SERIES_BINDING_REGISTRY.get(binding_id)
    if binding is None:
        raise ValueError(f"Unknown character-series binding: {binding_id}")
    return binding.model_copy(deep=True)


def get_character_series_binding_for_pair(
    *,
    character_id: str,
    series_style_id: str,
) -> CharacterSeriesBindingEntry:
    binding = _get_binding_by_character_and_style(
        character_id=character_id,
        series_style_id=series_style_id,
    )
    if binding is None:
        raise ValueError(
            "Unknown character-series binding for pair: "
            f"{character_id} + {series_style_id}"
        )
    return binding.model_copy(deep=True)
