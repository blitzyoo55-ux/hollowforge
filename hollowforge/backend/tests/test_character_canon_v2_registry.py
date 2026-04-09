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
    assert "glamour" not in camila.identity_anchor.lower()


def test_camila_v2_character_canon_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="Unknown character canon V2"):
        get_character_canon_v2(character_id="missing_camila")
