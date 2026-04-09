"""Panel-role aware comic render profile registry."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ComicPanelRenderProfile:
    profile_id: str
    panel_types: tuple[str, ...]
    lora_mode: str
    width: int
    height: int
    negative_prompt_append: str
    anchor_filter_mode: str
    prompt_order_mode: str = "default_subject_first"
    subject_prominence_mode: str = "default"
    scene_cue_mode: str = "none"


_BEAUTY_ENHANCER_MARKERS = (
    "detaileyes",
    "detailedeyes",
    "faceenhancer",
    "faceenhance",
    "beautyenhancer",
    "portraitenhancer",
    "eyeenhancer",
)


_ANCHOR_FILTER_MARKERS: dict[str, tuple[str, ...]] = {
    "drop_portrait_bias": (
        "glamorous adult woman",
        "high-response beauty editorial",
        "beauty editorial",
        "strong eye contact",
        "luminous skin",
        "refined facial features",
        "refined facial structure",
        "high-fashion poise",
        "elegant proportions",
        "glamour shoot",
        "glamour pose",
        "fashion shoot",
        "fashion editorial",
        "close portrait",
        "airbrushed skin",
        "copy-paste framing",
        "copy-paste composition",
    ),
    "drop_face_gloss_bias": (
        "glamorous adult woman",
        "high-response beauty editorial",
        "beauty editorial",
        "strong eye contact",
        "luminous skin",
        "refined facial features",
        "refined facial structure",
        "high-fashion poise",
        "elegant proportions",
        "glossy face",
        "waxy skin",
        "waxy face",
        "plastic skin",
        "dead eyes",
        "airbrushed skin",
    ),
}


def _normalize_filename(filename: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", filename.lower())


def _normalize_anchor_fragment(fragment: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", fragment.lower())


def _should_drop_anchor_fragment(fragment: str, *, anchor_filter_mode: str) -> bool:
    markers = _ANCHOR_FILTER_MARKERS.get(anchor_filter_mode)
    if not markers:
        return False
    normalized_fragment = _normalize_anchor_fragment(fragment)
    if any(
        _normalize_anchor_fragment(marker) in normalized_fragment
        for marker in markers
    ):
        return True

    if anchor_filter_mode == "drop_portrait_bias":
        glamour_terms = ("glamour", "glamorous")
        bias_modifiers = (
            "beauty",
            "editorial",
            "fashion",
            "shoot",
            "shooting",
            "portrait",
            "pose",
            "headshot",
            "closeup",
            "closeup",
        )
        if any(term in normalized_fragment for term in glamour_terms) and any(
            modifier in normalized_fragment for modifier in bias_modifiers
        ):
            return True
        if "beauty" in normalized_fragment and any(
            modifier in normalized_fragment
            for modifier in ("editorial", "fashion", "shoot", "portrait", "pose")
        ):
            return True

    return False


def filter_anchor_fragments(
    fragments: list[str],
    *,
    anchor_filter_mode: str,
) -> list[str]:
    if anchor_filter_mode not in _ANCHOR_FILTER_MARKERS:
        return [fragment for fragment in fragments if fragment.strip()]

    filtered: list[str] = []
    for fragment in fragments:
        cleaned = fragment.strip()
        if not cleaned:
            continue
        if _should_drop_anchor_fragment(cleaned, anchor_filter_mode=anchor_filter_mode):
            continue
        filtered.append(cleaned)
    return filtered


def _make_profile(
    profile_id: str,
    panel_types: tuple[str, ...],
    *,
    lora_mode: str,
    width: int,
    height: int,
    negative_prompt_append: str,
    anchor_filter_mode: str,
    prompt_order_mode: str = "default_subject_first",
    subject_prominence_mode: str = "default",
    scene_cue_mode: str = "none",
) -> ComicPanelRenderProfile:
    return ComicPanelRenderProfile(
        profile_id=profile_id,
        panel_types=panel_types,
        lora_mode=lora_mode,
        width=width,
        height=height,
        negative_prompt_append=negative_prompt_append,
        anchor_filter_mode=anchor_filter_mode,
        prompt_order_mode=prompt_order_mode,
        subject_prominence_mode=subject_prominence_mode,
        scene_cue_mode=scene_cue_mode,
    )


_PROFILE_REGISTRY: tuple[ComicPanelRenderProfile, ...] = (
    _make_profile(
        "establish_env_v2",
        ("establish",),
        lora_mode="filter_beauty_enhancers",
        width=1216,
        height=832,
        negative_prompt_append=(
            "glamour shoot, fashion editorial, close portrait, airbrushed skin, "
            "copy-paste composition, single-subject glamour poster, pinup composition, "
            "beauty key visual, empty background, minimal room detail, subject filling frame"
        ),
        anchor_filter_mode="drop_portrait_bias",
        prompt_order_mode="scene_first",
        subject_prominence_mode="reduced",
        scene_cue_mode="artist_loft_scene_cues",
    ),
    _make_profile(
        "beat_dialogue_v1",
        ("beat",),
        lora_mode="inherit_all",
        width=960,
        height=1216,
        negative_prompt_append="",
        anchor_filter_mode="drop_face_gloss_bias",
    ),
    _make_profile(
        "insert_prop_v1",
        ("insert",),
        lora_mode="filter_beauty_enhancers",
        width=1024,
        height=1024,
        negative_prompt_append="glamour shoot, fashion editorial, close portrait, airbrushed skin, copy-paste composition",
        anchor_filter_mode="drop_portrait_bias",
    ),
    _make_profile(
        "closeup_emotion_v1",
        ("closeup",),
        lora_mode="inherit_all",
        width=832,
        height=1216,
        negative_prompt_append="plastic skin, waxy face, dead eyes",
        anchor_filter_mode="drop_face_gloss_bias",
    ),
)

_PROFILE_BY_PANEL_TYPE: dict[str, ComicPanelRenderProfile] = {
    panel_type: profile
    for profile in _PROFILE_REGISTRY
    for panel_type in profile.panel_types
}


def resolve_comic_panel_render_profile(
    context: dict[str, object],
) -> ComicPanelRenderProfile:
    panel_type = str(context.get("panel_type") or "").strip().lower()
    profile = _PROFILE_BY_PANEL_TYPE.get(panel_type)
    if profile is not None:
        return profile
    return _PROFILE_BY_PANEL_TYPE["beat"]


def select_scene_cues(
    location: dict[str, object] | None,
    *,
    scene_cue_mode: str,
) -> list[str]:
    if scene_cue_mode != "artist_loft_scene_cues" or not location:
        return []

    raw_scene_cues = location.get("scene_cues")
    if not isinstance(raw_scene_cues, list):
        return []

    scene_cues = [str(cue).strip() for cue in raw_scene_cues if str(cue).strip()]
    return scene_cues[:2]


def filter_profile_loras(
    loras: list[dict[str, object]],
    *,
    lora_mode: str,
) -> list[dict[str, object]]:
    if lora_mode != "filter_beauty_enhancers":
        return [dict(lora) for lora in loras]

    filtered: list[dict[str, object]] = []
    for lora in loras:
        filename = str(lora.get("filename") or "")
        normalized = _normalize_filename(filename)
        if any(marker in normalized for marker in _BEAUTY_ENHANCER_MARKERS):
            continue
        filtered.append(dict(lora))
    return filtered
