"""Registry for the Camila V2 character canon pilot."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CharacterCanonV2Entry(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    identity_anchor: str = Field(min_length=1, max_length=1000)
    face_structure_notes: str = Field(min_length=1, max_length=1000)
    eye_signature: str = Field(min_length=1, max_length=1000)
    hair_signature: str = Field(min_length=1, max_length=1000)
    skin_surface_policy: str = Field(min_length=1, max_length=1000)
    body_signature: str = Field(min_length=1, max_length=1000)
    expression_range: str = Field(min_length=1, max_length=1000)
    identity_negative_rules: str = Field(min_length=1, max_length=1000)
    anti_drift: str = Field(min_length=1, max_length=1000)
    wardrobe_notes: str = Field(min_length=1, max_length=600)
    personality_notes: str = Field(min_length=1, max_length=600)


_CHARACTER_CANON_V2_REGISTRY: dict[str, CharacterCanonV2Entry] = {
    "camila_v2": CharacterCanonV2Entry(
        id="camila_v2",
        name="Camila",
        identity_anchor="Camila, poised adult woman with a practical, grounded presence",
        face_structure_notes=(
            "Defined but natural face structure with calm proportions and stable "
            "recognition."
        ),
        eye_signature=(
            "Clear, attentive eyes with a steady directness and consistent gaze."
        ),
        hair_signature=(
            "Practical, low-fuss hair that reads as lived-in and controlled."
        ),
        skin_surface_policy=(
            "Preserve a natural skin surface with light texture and avoid oversmoothing."
        ),
        body_signature=(
            "Adult, grounded build with believable presence and balanced posture."
        ),
        expression_range=(
            "Calm, observant, and direct with small controlled shifts in emotion."
        ),
        identity_negative_rules=(
            "No glamour styling, no editorial beauty language, no resort presentation, "
            "no model-pose drift."
        ),
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


def get_character_canon_v2(character_id: str) -> CharacterCanonV2Entry:
    entry = _CHARACTER_CANON_V2_REGISTRY.get(character_id)
    if entry is None:
        raise ValueError(f"Unknown character canon V2: {character_id}")
    return entry.model_copy(deep=True)
