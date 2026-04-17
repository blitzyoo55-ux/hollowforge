from __future__ import annotations

from app.services.comic_render_profiles import (
    filter_anchor_fragments,
    filter_profile_loras,
    select_scene_cues,
    resolve_comic_panel_render_profile,
)


def test_resolve_profile_returns_establish_env_profile_for_establish_panel() -> None:
    profile = resolve_comic_panel_render_profile({"panel_type": "establish"})

    assert profile.profile_id == "establish_env_v2"
    assert profile.width == 1216
    assert profile.height == 832
    assert profile.lora_mode == "inherit_all"
    assert profile.prompt_order_mode == "scene_first"
    assert profile.subject_prominence_mode == "reduced"
    assert profile.scene_cue_mode == "artist_loft_scene_cues"


def test_select_scene_cues_returns_artist_loft_morning_scene_cues_in_order() -> None:
    location = {
        "id": "artist_loft_morning",
        "scene_cues": [
            "tall factory windows",
            "easel",
            "canvas",
            "worktable",
            "coffee mug",
            "sketchbook",
        ],
    }

    assert select_scene_cues(location, scene_cue_mode="artist_loft_scene_cues") == [
        "tall factory windows",
        "easel",
    ]


def test_select_scene_cues_returns_empty_list_when_location_has_no_scene_cues() -> None:
    assert select_scene_cues(
        {"id": "artist_loft_morning"},
        scene_cue_mode="artist_loft_scene_cues",
    ) == []


def test_select_scene_cues_returns_empty_list_for_non_loft_locations() -> None:
    assert select_scene_cues(
        {
            "id": "moonlit_bathhouse",
            "scene_cues": ["polished stone", "steam-softened light"],
        },
        scene_cue_mode="artist_loft_scene_cues",
    ) == []


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


def test_filter_anchor_fragments_drops_portrait_bias() -> None:
    fragments = [
        "masterpiece",
        "best quality",
        "brazilian glamour beauty",
        "warm hazel eyes",
        "elegant proportions",
    ]

    filtered = filter_anchor_fragments(
        fragments,
        anchor_filter_mode="drop_portrait_bias",
    )

    assert filtered == ["masterpiece", "best quality", "warm hazel eyes"]


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


def test_profiles_expose_role_quality_selector_hints() -> None:
    establish = resolve_comic_panel_render_profile({"panel_type": "establish"})
    beat = resolve_comic_panel_render_profile({"panel_type": "beat"})
    insert = resolve_comic_panel_render_profile({"panel_type": "insert"})
    closeup = resolve_comic_panel_render_profile({"panel_type": "closeup"})

    assert establish.quality_selector_hints == (
        "room readability",
        "reduced subject occupancy",
        "environment depth",
    )
    assert beat.quality_selector_hints == (
        "expression readability",
        "natural body pose",
        "clear hand acting",
    )
    assert insert.quality_selector_hints == (
        "prop readability",
        "action readability",
        "hand-prop contact",
    )
    assert closeup.quality_selector_hints == (
        "emotion clarity",
        "alive eyes",
        "artifact suppression",
    )


def test_profiles_expose_role_quality_recipe_families() -> None:
    establish = resolve_comic_panel_render_profile({"panel_type": "establish"})
    beat = resolve_comic_panel_render_profile({"panel_type": "beat"})
    insert = resolve_comic_panel_render_profile({"panel_type": "insert"})
    closeup = resolve_comic_panel_render_profile({"panel_type": "closeup"})

    assert establish.quality_recipe_family == "room_safe"
    assert beat.quality_recipe_family == "lifestyle_safe"
    assert insert.quality_recipe_family == "comic_close_safe"
    assert closeup.quality_recipe_family == "comic_close_safe"


def test_role_negatives_penalize_glamour_poster_failure_patterns() -> None:
    establish = resolve_comic_panel_render_profile({"panel_type": "establish"})
    beat = resolve_comic_panel_render_profile({"panel_type": "beat"})
    insert = resolve_comic_panel_render_profile({"panel_type": "insert"})
    closeup = resolve_comic_panel_render_profile({"panel_type": "closeup"})

    assert "single-subject glamour poster" in establish.negative_prompt_append
    assert "beauty key visual" in establish.negative_prompt_append
    assert "single-subject glamour poster" in beat.negative_prompt_append
    assert "beauty key visual" in beat.negative_prompt_append
    assert "single-subject glamour poster" in insert.negative_prompt_append
    assert "beauty key visual" in insert.negative_prompt_append
    assert "dead eyes" in closeup.negative_prompt_append
