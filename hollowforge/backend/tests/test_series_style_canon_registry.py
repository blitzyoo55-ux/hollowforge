from __future__ import annotations

import pytest

from app.services.series_style_canon_registry import get_series_style_canon


def test_load_pilot_series_style_canon_by_id() -> None:
    style = get_series_style_canon(series_style_id="camila_pilot_v1")

    assert style.id == "camila_pilot_v1"
    assert style.display_name == "Camila Pilot V1"
    assert style.teaser_motion_policy == "static_hero"
    assert style.notes == "Pilot series style canon for the Camila-only V2 pilot."


def test_load_test_only_series_style_canon_uses_different_teaser_motion_policy() -> None:
    pilot = get_series_style_canon(series_style_id="camila_pilot_v1")
    test_only = get_series_style_canon(series_style_id="camila_motion_test_v1")

    assert pilot.teaser_motion_policy != test_only.teaser_motion_policy
    assert test_only.teaser_motion_policy == "subtle_loop"
    assert test_only.display_name == "Camila Motion Test V1"
    assert test_only.notes == (
        "Test-only alternate style used to validate teaser motion policy "
        "variance."
    )


def test_series_style_canon_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="Unknown series style canon"):
        get_series_style_canon(series_style_id="missing_style")
