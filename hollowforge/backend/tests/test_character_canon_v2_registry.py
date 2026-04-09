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
    assert "glamour" not in camila.identity_anchor.lower()


def test_camila_v2_character_canon_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="Unknown character canon V2"):
        get_character_canon_v2(character_id="missing_camila")
