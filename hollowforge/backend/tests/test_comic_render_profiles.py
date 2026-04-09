from __future__ import annotations

from app.services.comic_render_profiles import (
    filter_profile_loras,
    resolve_comic_panel_render_profile,
)


def test_resolve_profile_returns_establish_env_profile_for_establish_panel() -> None:
    profile = resolve_comic_panel_render_profile({"panel_type": "establish"})

    assert profile.profile_id == "establish_env_v1"
    assert profile.width == 1216
    assert profile.height == 832


def test_establish_profile_filters_beauty_enhancers() -> None:
    filtered = filter_profile_loras(
        [
            {"filename": "DetailedEyes_V3", "strength": 0.45},
            {"filename": "Face_Enhancer_Illustrious", "strength": 0.36},
        ],
        lora_mode="filter_beauty_enhancers",
    )

    assert filtered == []


def test_closeup_profile_keeps_identity_loras() -> None:
    profile = resolve_comic_panel_render_profile({"panel_type": "closeup"})

    assert profile.profile_id == "closeup_emotion_v1"
    assert profile.lora_mode == "inherit_all"
