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


def test_resolve_profile_returns_beat_dialogue_profile_for_beat_panel() -> None:
    profile = resolve_comic_panel_render_profile({"panel_type": "beat"})

    assert profile.profile_id == "beat_dialogue_v1"
    assert profile.width == 960
    assert profile.height == 1216
    assert profile.lora_mode == "inherit_all"


def test_resolve_profile_returns_insert_prop_profile_for_insert_panel() -> None:
    profile = resolve_comic_panel_render_profile({"panel_type": "insert"})

    assert profile.profile_id == "insert_prop_v1"
    assert profile.width == 1024
    assert profile.height == 1024
    assert profile.lora_mode == "filter_beauty_enhancers"


def test_resolve_profile_falls_back_to_beat_profile_for_unknown_panel_type() -> None:
    profile = resolve_comic_panel_render_profile({"panel_type": "unknown"})

    assert profile.profile_id == "beat_dialogue_v1"
    assert profile.width == 960
    assert profile.height == 1216


def test_establish_profile_filters_beauty_enhancers() -> None:
    filtered = filter_profile_loras(
        [
            {"filename": "DetailedEyes_V3", "strength": 0.45},
            {"filename": "Face_Enhancer_Illustrious", "strength": 0.36},
        ],
        lora_mode="filter_beauty_enhancers",
    )

    assert filtered == []


def test_filter_profile_loras_keeps_non_enhancers_in_mixed_filter_mode() -> None:
    loras = [
        {"filename": "DetailedEyes_V3", "strength": 0.45},
        {"filename": "Scene_Anchor_Concept", "strength": 0.7},
        {"filename": "Face_Enhancer_Illustrious", "strength": 0.36},
    ]

    filtered = filter_profile_loras(loras, lora_mode="filter_beauty_enhancers")

    assert filtered == [{"filename": "Scene_Anchor_Concept", "strength": 0.7}]


def test_closeup_profile_keeps_identity_loras() -> None:
    profile = resolve_comic_panel_render_profile({"panel_type": "closeup"})

    assert profile.profile_id == "closeup_emotion_v1"
    assert profile.lora_mode == "inherit_all"


def test_filter_profile_loras_passthrough_preserves_inherit_all_loras() -> None:
    loras = [
        {"filename": "DetailedEyes_V3", "strength": 0.45},
        {"filename": "Scene_Anchor_Concept", "strength": 0.7},
    ]

    filtered = filter_profile_loras(loras, lora_mode="inherit_all")

    assert filtered == loras
