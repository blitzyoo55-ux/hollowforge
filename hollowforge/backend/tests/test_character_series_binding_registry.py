from __future__ import annotations

import pytest

from app.services.character_series_binding_registry import (
    _CHARACTER_SERIES_BINDING_REGISTRY,
    _validate_binding_registry_pairs,
    get_character_series_binding,
    get_character_series_binding_for_pair,
)
from app.services.character_canon_v2_registry import get_character_canon_v2
from app.services.series_style_canon_registry import get_series_style_canon


def test_load_camila_binding_by_explicit_id() -> None:
    binding = get_character_series_binding("camila_pilot_binding_v1")

    assert binding.id == "camila_pilot_binding_v1"
    assert binding.character_id == "camila_v2"
    assert binding.series_style_id == "camila_pilot_v1"
    assert binding.notes == "Camila-only pilot binding for the V2 registry pilot."
    assert binding.identity_lock_strength == "strong"
    assert binding.hair_lock_strength == "strong"
    assert binding.face_lock_strength == "strong"
    assert binding.allowed_wardrobe_family == (
        "simple functional everyday wardrobe"
    )
    assert binding.binding_negative_rules == (
        "No wardrobe drift, no glamour drift, no editorial styling drift."
    )
    assert binding.do_not_mutate == (
        "Do not mutate Camila identity ownership, style ownership, or checkpoint "
        "ownership through this binding."
    )


def test_load_camila_binding_by_pair_lookup() -> None:
    binding = get_character_series_binding_for_pair(
        character_id="camila_v2",
        series_style_id="camila_pilot_v1",
    )

    assert binding.id == "camila_pilot_binding_v1"


def test_camila_binding_points_at_real_registry_entries() -> None:
    binding = get_character_series_binding("camila_pilot_binding_v1")
    camila = get_character_canon_v2(binding.character_id)
    series_style = get_series_style_canon(binding.series_style_id)

    assert camila.id == binding.character_id
    assert series_style.id == binding.series_style_id
    assert camila.name == "Camila"
    assert series_style.display_name == "Camila Pilot V1"


def test_character_series_binding_pair_lookup_rejects_unknown_pair() -> None:
    with pytest.raises(ValueError, match="Unknown character-series binding for pair"):
        get_character_series_binding_for_pair(
            character_id="camila_v2",
            series_style_id="camila_motion_test_v1",
        )


def test_character_series_binding_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="Unknown character-series binding"):
        get_character_series_binding("missing_binding")


def test_character_series_binding_registry_rejects_duplicate_character_style_pairs() -> None:
    duplicate_registry = {
        "camila_pilot_binding_v1": _CHARACTER_SERIES_BINDING_REGISTRY[
            "camila_pilot_binding_v1"
        ],
        "camila_pilot_binding_v2": _CHARACTER_SERIES_BINDING_REGISTRY[
            "camila_pilot_binding_v1"
        ].model_copy(update={"id": "camila_pilot_binding_v2"}),
    }

    original_registry = dict(_CHARACTER_SERIES_BINDING_REGISTRY)
    try:
        _CHARACTER_SERIES_BINDING_REGISTRY.clear()
        _CHARACTER_SERIES_BINDING_REGISTRY.update(duplicate_registry)
        with pytest.raises(RuntimeError, match="Duplicate character-series binding pair"):
            _validate_binding_registry_pairs()
    finally:
        _CHARACTER_SERIES_BINDING_REGISTRY.clear()
        _CHARACTER_SERIES_BINDING_REGISTRY.update(original_registry)
