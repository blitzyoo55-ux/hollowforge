from __future__ import annotations

import pytest

from app.services.character_canon_v2_registry import get_character_canon_v2


def test_load_camila_v2_character_canon_by_id() -> None:
    camila = get_character_canon_v2(character_id="camila_v2")

    assert camila.id == "camila_v2"
    assert camila.name == "Camila"
    assert camila.identity_anchor == (
        "Camila Duarte, adult Brazilian woman with warm sun-kissed tan skin, "
        "long chestnut-brown wavy hair, and a naturally elegant grounded presence"
    )
    assert camila.anti_drift == (
        "Keep Camila anchored in a calm, grounded, adult non-glamour identity. "
        "Avoid drifting into editorial beauty framing, school-uniform styling, "
        "or youthful heroine shortcuts."
    )
    assert camila.wardrobe_notes == (
        "Simple studio-casual wardrobe such as soft knits, open-collar shirts, "
        "relaxed adult blouses, or understated camisoles layered under cardigans; "
        "never schoolwear trims, ribbon ties, or costume-coded accents."
    )
    assert camila.personality_notes == (
        "Measured, observant, and direct; she reads as self-possessed, mature, "
        "grounded, and quietly alluring through confidence rather than performance."
    )
    assert camila.reference_descriptor_notes == (
        "Chestnut-brown hair with warm highlights, lightly tanned skin, and a "
        "mature calm presence with natural elegance. Reject school-uniform and "
        "youth-coded drift."
    )
    assert camila.reference_hair_brightness_range == (0.14, 0.48)
    assert camila.reference_hair_warmth_range == (0.03, 0.28)
    assert camila.reference_skin_brightness_range == (0.45, 0.82)
    assert camila.reference_skin_warmth_range == (0.03, 0.24)
    assert camila.forbidden_wardrobe_tags == (
        "school_uniform",
        "serafuku",
        "sailor_collar",
        "necktie",
        "bow",
        "hair_bow",
        "neck_ribbon",
        "ribbon",
        "plaid_skirt",
    )
    assert camila.forbidden_youth_tags == (
        "child",
        "loli",
        "young",
        "petite",
        "school_uniform",
    )
    assert camila.face_structure_notes == (
        "Graceful adult face structure with calm cheekbone and jawline balance, "
        "stable recognition, and no youthful simplification."
    )
    assert camila.eye_signature == (
        "Warm hazel eyes with steady directness, calm confidence, and adult warmth."
    )
    assert camila.hair_signature == (
        "Long chestnut-brown waves with warm highlights; never orange, blonde, "
        "or school-idol styled."
    )
    assert camila.skin_surface_policy == (
        "Preserve a natural lightly tanned skin surface with warm undertone, "
        "light texture, healthy warmth, and no oversmoothing."
    )
    assert camila.body_signature == (
        "Adult grounded build with believable feminine presence, balanced posture, "
        "healthy proportions, and no youth-coded silhouette."
    )
    assert camila.expression_range == (
        "Calm, observant, and direct with small controlled shifts in emotion."
    )
    assert camila.adult_appeal_notes == (
        "Composed mature beauty, approachable warmth, and quietly magnetic adult "
        "presence; attractive without glamour posing or teen-coded stylization."
    )
    assert camila.identity_negative_rules == (
        "No glamour styling, no editorial beauty language, no resort presentation, "
        "no model-pose drift, no school-uniform cues, no necktie, no orange hair, "
        "no youth-coded anime heroine drift."
    )
    for field_name in (
        "identity_anchor",
        "face_structure_notes",
        "eye_signature",
        "hair_signature",
        "skin_surface_policy",
        "body_signature",
        "expression_range",
    ):
        field_value = getattr(camila, field_name).lower()
        assert "glamour" not in field_value
        assert "editorial" not in field_value
        assert "resort" not in field_value


def test_camila_v2_character_canon_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="Unknown character canon V2"):
        get_character_canon_v2(character_id="missing_camila")
