"""Resolver for comic render V2 contract sections."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.character_canon_v2_registry import get_character_canon_v2
from app.services.character_series_binding_registry import get_character_series_binding
from app.services.comic_render_profiles import ComicPanelRenderProfile
from app.services.series_style_canon_registry import get_series_style_canon


class ComicRenderV2Contract(BaseModel):
    model_config = {"extra": "forbid", "frozen": True}

    identity_block: tuple[str, ...]
    style_block: tuple[str, ...]
    binding_block: tuple[str, ...]
    role_block: tuple[str, ...]
    execution_params: dict[str, Any] = Field(default_factory=dict)
    negative_rules: tuple[str, ...]


_STYLE_EXECUTION_REGISTRY: dict[str, dict[str, Any]] = {
    "camila_pilot_v1": {
        "checkpoint": "waiIllustriousSDXL_v160.safetensors",
        "loras": (
            {
                "filename": "camila_pilot_line_treatment_v1.safetensors",
                "strength": 0.65,
            },
        ),
        "steps": 30,
        "cfg": 5.4,
        "sampler": "euler_a",
        "style_artifact_negative": (
            "Avoid style artifacts: over-sharpened outlines, posterized gradients, "
            "muddy midtones."
        ),
    },
    "camila_motion_test_v1": {
        "checkpoint": "waiIllustriousSDXL_v160.safetensors",
        "loras": (
            {
                "filename": "camila_motion_test_line_treatment_v1.safetensors",
                "strength": 0.62,
            },
        ),
        "steps": 28,
        "cfg": 5.2,
        "sampler": "euler_a",
        "style_artifact_negative": (
            "Avoid style artifacts: unstable line cadence, temporal shimmer, muddy "
            "midtones."
        ),
    },
}

_BINDING_EXECUTION_REGISTRY: dict[str, dict[str, float]] = {
    "camila_pilot_binding_v1": {
        "identity_lock_strength": 0.92,
        "style_lock_strength": 0.88,
    }
}

_DEFAULT_BINDING_LOCK_STRENGTHS: dict[str, float] = {
    "identity_lock_strength": 0.9,
    "style_lock_strength": 0.85,
}

_DEFAULT_STYLE_EXECUTION_TEMPLATE: dict[str, Any] = {
    "checkpoint": "waiIllustriousSDXL_v160.safetensors",
    "loras": (),
    "steps": 30,
    "cfg": 5.4,
    "sampler": "euler_a",
    "style_artifact_negative": (
        "Avoid style artifacts: over-sharpened outlines, posterized gradients, "
        "muddy midtones."
    ),
}


def _resolve_style_execution_params(series_style_id: str) -> dict[str, Any]:
    resolved = dict(_DEFAULT_STYLE_EXECUTION_TEMPLATE)
    resolved.update(_STYLE_EXECUTION_REGISTRY.get(series_style_id, {}))
    return resolved


def resolve_comic_render_v2_contract(
    *,
    character_id: str,
    series_style_id: str,
    binding_id: str,
    panel_type: str,
    location_label: str | None,
    continuity_notes: str | None,
    role_profile: ComicPanelRenderProfile,
) -> ComicRenderV2Contract:
    character = get_character_canon_v2(character_id)
    style = get_series_style_canon(series_style_id)
    binding = get_character_series_binding(binding_id)

    if binding.character_id != character_id:
        raise ValueError(
            f"Binding {binding_id} does not match character {character_id}"
        )
    if binding.series_style_id != series_style_id:
        raise ValueError(
            f"Binding {binding_id} does not match series style {series_style_id}"
        )

    role_block = (
        f"Panel type: {panel_type}",
        f"Role profile: {role_profile.profile_id}",
    )
    identity_block = (
        character.identity_anchor,
        character.wardrobe_notes,
        character.personality_notes,
    )
    style_block = (
        f"Series style: {style.display_name}",
        f"Style notes: {style.notes}",
    )

    binding_fragments: list[str] = [f"Binding notes: {binding.notes}"]
    if location_label and location_label.strip():
        binding_fragments.append(f"Location: {location_label.strip()}")
    if continuity_notes and continuity_notes.strip():
        binding_fragments.append(f"Continuity: {continuity_notes.strip()}")
    binding_block = tuple(binding_fragments)

    style_execution = _resolve_style_execution_params(series_style_id)

    # Precedence: style execution params -> binding lock strengths -> role defaults.
    execution_params: dict[str, Any] = {
        "checkpoint": style_execution["checkpoint"],
        "loras": style_execution["loras"],
        "steps": style_execution["steps"],
        "cfg": style_execution["cfg"],
        "sampler": style_execution["sampler"],
    }
    execution_params.update(
        _BINDING_EXECUTION_REGISTRY.get(binding_id, _DEFAULT_BINDING_LOCK_STRENGTHS)
    )
    execution_params.setdefault("width", role_profile.width)
    execution_params.setdefault("height", role_profile.height)
    execution_params.setdefault("framing_profile", role_profile.profile_id)

    negative_rules = (
        style_execution["style_artifact_negative"],
        character.anti_drift,
        "Binding negative: do not swap character identity or style assignment outside this binding.",
        f"Role negative: {role_profile.negative_prompt_append}",
    )

    return ComicRenderV2Contract(
        identity_block=identity_block,
        style_block=style_block,
        binding_block=binding_block,
        role_block=role_block,
        execution_params=execution_params,
        negative_rules=negative_rules,
    )
