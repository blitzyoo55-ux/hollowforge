from __future__ import annotations

import pytest

from app.services.series_style_canon_registry import get_series_style_canon


def test_load_pilot_series_style_canon_by_id() -> None:
    style = get_series_style_canon("camila_pilot_v1")

    assert style.id == "camila_pilot_v1"
    assert style.teaser_motion_policy == "static_hero"


def test_load_test_only_series_style_canon_uses_different_teaser_motion_policy() -> None:
    pilot = get_series_style_canon("camila_pilot_v1")
    test_only = get_series_style_canon("camila_motion_test_v1")

    assert pilot.teaser_motion_policy != test_only.teaser_motion_policy
    assert test_only.teaser_motion_policy == "subtle_loop"


def test_series_style_canon_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="Unknown series style canon"):
        get_series_style_canon("missing_style")
