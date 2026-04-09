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


_BEAUTY_ENHANCER_MARKERS = (
    "detaileyes",
    "detailedeyes",
    "faceenhancer",
    "faceenhance",
    "beautyenhancer",
    "portraitenhancer",
    "eyeenhancer",
)

_SUPPORTED_LORA_MODES = {
    "inherit_all",
    "filter_beauty_enhancers",
}


def _normalize_filename(filename: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", filename.lower())


def _make_profile(
    profile_id: str,
    panel_types: tuple[str, ...],
    *,
    lora_mode: str,
    width: int,
    height: int,
    negative_prompt_append: str,
    anchor_filter_mode: str,
) -> ComicPanelRenderProfile:
    return ComicPanelRenderProfile(
        profile_id=profile_id,
        panel_types=panel_types,
        lora_mode=lora_mode,
        width=width,
        height=height,
        negative_prompt_append=negative_prompt_append,
        anchor_filter_mode=anchor_filter_mode,
    )


_PROFILE_REGISTRY: tuple[ComicPanelRenderProfile, ...] = (
    _make_profile(
        "establish_env_v1",
        ("establish", "splash"),
        lora_mode="filter_beauty_enhancers",
        width=1216,
        height=832,
        negative_prompt_append="close portrait, fashion shoot, glamour pose, airbrushed skin, copy-paste framing",
        anchor_filter_mode="drop_portrait_bias",
    ),
    _make_profile(
        "beat_dialogue_v1",
        ("beat", "transition"),
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
        negative_prompt_append="close portrait, fashion shoot, glamour pose, airbrushed skin, copy-paste framing",
        anchor_filter_mode="drop_portrait_bias",
    ),
    _make_profile(
        "closeup_emotion_v1",
        ("closeup",),
        lora_mode="inherit_all",
        width=832,
        height=1216,
        negative_prompt_append="dead eyes, waxy skin, plastic skin, glossy face",
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


def filter_profile_loras(
    loras: list[dict[str, object]],
    *,
    lora_mode: str,
) -> list[dict[str, object]]:
    if lora_mode not in _SUPPORTED_LORA_MODES:
        raise ValueError(f"Unsupported comic panel lora_mode: {lora_mode}")

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
