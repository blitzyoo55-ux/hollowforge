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
    adult_appeal_notes: str = Field(min_length=1, max_length=1000)
    identity_negative_rules: str = Field(min_length=1, max_length=1000)
    anti_drift: str = Field(min_length=1, max_length=1000)
    wardrobe_notes: str = Field(min_length=1, max_length=600)
    personality_notes: str = Field(min_length=1, max_length=600)
    reference_descriptor_notes: str = Field(min_length=1, max_length=600)
    reference_hair_brightness_range: tuple[float, float]
    reference_hair_warmth_range: tuple[float, float]
    reference_skin_brightness_range: tuple[float, float]
    reference_skin_warmth_range: tuple[float, float]
    forbidden_wardrobe_tags: tuple[str, ...] = Field(default_factory=tuple)
    forbidden_youth_tags: tuple[str, ...] = Field(default_factory=tuple)


_CHARACTER_CANON_V2_REGISTRY: dict[str, CharacterCanonV2Entry] = {
    "camila_v2": CharacterCanonV2Entry(
        id="camila_v2",
        name="Camila",
        identity_anchor=(
            "Camila Duarte, adult Brazilian woman with warm sun-kissed tan skin, "
            "long chestnut-brown wavy hair, and a naturally elegant grounded presence"
        ),
        face_structure_notes=(
            "Graceful adult face structure with calm cheekbone and jawline balance, "
            "stable recognition, and no youthful simplification."
        ),
        eye_signature=(
            "Warm hazel eyes with steady directness, calm confidence, and adult warmth."
        ),
        hair_signature=(
            "Long chestnut-brown waves with warm highlights; never orange, blonde, "
            "or school-idol styled."
        ),
        skin_surface_policy=(
            "Preserve a natural lightly tanned skin surface with warm undertone, "
            "light texture, healthy warmth, and no oversmoothing."
        ),
        body_signature=(
            "Adult grounded build with believable feminine presence, balanced posture, "
            "healthy proportions, and no youth-coded silhouette."
        ),
        expression_range=(
            "Calm, observant, and direct with small controlled shifts in emotion."
        ),
        adult_appeal_notes=(
            "Composed mature beauty, approachable warmth, and quietly magnetic adult "
            "presence; attractive without glamour posing or teen-coded stylization."
        ),
        identity_negative_rules=(
            "No glamour styling, no editorial beauty language, no resort presentation, "
            "no model-pose drift, no school-uniform cues, no necktie, no orange hair, "
            "no youth-coded anime heroine drift."
        ),
        anti_drift=(
            "Keep Camila anchored in a calm, grounded, adult non-glamour identity. "
            "Avoid drifting into editorial beauty framing, school-uniform styling, "
            "or youthful heroine shortcuts."
        ),
        wardrobe_notes=(
            "Simple studio-casual wardrobe such as soft knits, open-collar shirts, "
            "relaxed adult blouses, or understated camisoles layered under cardigans; "
            "never schoolwear trims, ribbon ties, or costume-coded accents."
        ),
        personality_notes=(
            "Measured, observant, and direct; she reads as self-possessed, mature, "
            "grounded, and quietly alluring through confidence rather than performance."
        ),
        reference_descriptor_notes=(
            "Chestnut-brown hair with warm highlights, lightly tanned skin, and a "
            "mature calm presence with natural elegance. Reject school-uniform and "
            "youth-coded drift."
        ),
        reference_hair_brightness_range=(0.14, 0.48),
        reference_hair_warmth_range=(0.03, 0.28),
        reference_skin_brightness_range=(0.45, 0.82),
        reference_skin_warmth_range=(0.03, 0.24),
        forbidden_wardrobe_tags=(
            "school_uniform",
            "serafuku",
            "sailor_collar",
            "necktie",
            "bow",
            "hair_bow",
            "neck_ribbon",
            "ribbon",
            "plaid_skirt",
        ),
        forbidden_youth_tags=(
            "child",
            "loli",
            "young",
            "petite",
            "school_uniform",
        ),
    )
}


def get_character_canon_v2(character_id: str) -> CharacterCanonV2Entry:
    entry = _CHARACTER_CANON_V2_REGISTRY.get(character_id)
    if entry is None:
        raise ValueError(f"Unknown character canon V2: {character_id}")
    return entry.model_copy(deep=True)
