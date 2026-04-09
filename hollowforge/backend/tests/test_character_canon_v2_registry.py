from __future__ import annotations

import pytest

from app.services.character_canon_v2_registry import get_character_canon_v2


def test_load_camila_v2_character_canon_by_id() -> None:
    camila = get_character_canon_v2(character_id="camila_v2")

    assert camila.id == "camila_v2"
    assert camila.name == "Camila"
    assert camila.identity_anchor == (
        "Camila, poised adult woman with a practical, grounded presence"
    )
    assert camila.anti_drift == (
        "Keep Camila anchored in a calm, grounded, non-glamour identity. "
        "Avoid drifting into editorial beauty framing."
    )
    assert camila.wardrobe_notes == (
        "Simple, functional wardrobe choices that support the scene without "
        "turning her into a fashion portrait."
    )
    assert camila.personality_notes == (
        "Measured, observant, and direct; she reads as self-possessed rather "
        "than performatively styled."
    )
    assert camila.face_structure_notes == (
        "Defined but natural face structure with calm proportions and no "
        "beautification drift."
    )
    assert camila.eye_signature == (
        "Clear, attentive eyes with a steady directness rather than a posed "
        "fashion gaze."
    )
    assert camila.hair_signature == (
        "Practical, low-fuss hair that reads as lived-in and controlled without "
        "becoming editorial."
    )
    assert camila.skin_surface_policy == (
        "Preserve a natural skin surface with light texture and avoid airbrushed "
        "finish."
    )
    assert camila.body_signature == (
        "Adult, grounded build with believable presence and no exaggerated pose "
        "language."
    )
    assert camila.expression_range == (
        "Calm, observant, and direct with small controlled shifts in emotion."
    )
    assert camila.identity_negative_rules == (
        "No glamour styling, no editorial beauty language, no resort presentation, "
        "no model-pose drift."
    )
    assert "glamour" not in camila.identity_anchor.lower()
    assert "editorial" not in camila.identity_anchor.lower()
    assert "resort" not in camila.identity_anchor.lower()


def test_camila_v2_character_canon_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="Unknown character canon V2"):
        get_character_canon_v2(character_id="missing_camila")
