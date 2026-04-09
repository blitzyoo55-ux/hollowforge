from __future__ import annotations

import pytest

from app.services.character_series_binding_registry import (
    get_character_series_binding,
    get_character_series_binding_for_pair,
)


def test_load_camila_binding_by_explicit_id() -> None:
    binding = get_character_series_binding("camila_pilot_binding_v1")

    assert binding.id == "camila_pilot_binding_v1"
    assert binding.character_id == "camila_v2"
    assert binding.series_style_id == "camila_pilot_v1"


def test_load_camila_binding_by_pair_lookup() -> None:
    binding = get_character_series_binding_for_pair(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
    )

    assert binding.id == "camila_pilot_binding_v1"


def test_character_series_binding_pair_lookup_rejects_unknown_pair() -> None:
    with pytest.raises(ValueError, match="Unknown character-series binding for pair"):
        get_character_series_binding_for_pair(
            character_id="camila_v2",
            series_style_id="camila_motion_test_v1",
        )


def test_character_series_binding_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="Unknown character-series binding"):
        get_character_series_binding("missing_binding")
