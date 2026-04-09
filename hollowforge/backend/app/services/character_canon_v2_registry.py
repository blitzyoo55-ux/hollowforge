"""Registry for the Camila V2 character canon pilot."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CharacterCanonV2Entry(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    identity_anchor: str = Field(min_length=1, max_length=1000)
    anti_drift: str = Field(min_length=1, max_length=1000)
    wardrobe_notes: str = Field(min_length=1, max_length=600)
    personality_notes: str = Field(min_length=1, max_length=600)


_CHARACTER_CANON_V2_REGISTRY: dict[str, CharacterCanonV2Entry] = {
    "camila_v2": CharacterCanonV2Entry(
        id="camila_v2",
        name="Camila",
        identity_anchor="Camila, poised adult woman with a practical, grounded presence",
        anti_drift=(
            "Keep Camila anchored in a calm, grounded, non-glamour identity. "
            "Avoid drifting into editorial beauty framing."
        ),
        wardrobe_notes=(
            "Simple, functional wardrobe choices that support the scene without "
            "turning her into a fashion portrait."
        ),
        personality_notes=(
            "Measured, observant, and direct; she reads as self-possessed rather "
            "than performatively styled."
        ),
    )
}


def get_character_canon_v2(character_canon_v2_id: str) -> CharacterCanonV2Entry:
    entry = _CHARACTER_CANON_V2_REGISTRY.get(character_canon_v2_id)
    if entry is None:
        raise ValueError(f"Unknown character canon V2: {character_canon_v2_id}")
    return entry.model_copy(deep=True)
