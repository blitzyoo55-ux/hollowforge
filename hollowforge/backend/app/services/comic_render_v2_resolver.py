"""Resolver for comic render V2 contract sections."""

from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Any
from collections.abc import Mapping

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
    execution_params: Any = Field(default_factory=dict)
    negative_rules: tuple[str, ...]


_STYLE_EXECUTION_REGISTRY: dict[str, dict[str, Any]] = {
    "camila_pilot_v1": {
        "checkpoint": "prefectIllustriousXL_v70.safetensors",
        "loras": (
            {
                "filename": "DetailedEyes_V3.safetensors",
                "strength": 0.45,
            },
            {
                "filename": "Face_Enhancer_Illustrious.safetensors",
                "strength": 0.36,
            },
        ),
        "steps": 30,
        "cfg": 5.4,
        "sampler": "euler_a",
    },
    "camila_motion_test_v1": {
        "checkpoint": "prefectIllustriousXL_v70.safetensors",
        "loras": (
            {
                "filename": "DetailedEyes_V3.safetensors",
                "strength": 0.45,
            },
            {
                "filename": "Face_Enhancer_Illustrious.safetensors",
                "strength": 0.36,
            },
        ),
        "steps": 28,
        "cfg": 5.2,
        "sampler": "euler_a",
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

_POSITIVE_MERGE_SEQUENCE: tuple[str, ...] = (
    "role",
    "identity",
    "style",
    "binding",
    "continuity_location",
)

_NEGATIVE_MERGE_SEQUENCE: tuple[str, ...] = (
    "style_artifacts",
    "identity_drift",
    "binding_drift",
    "role_quality",
)

_REQUIRED_STYLE_EXECUTION_KEYS: tuple[str, ...] = (
    "checkpoint",
    "loras",
    "steps",
    "cfg",
    "sampler",
)


def _resolve_style_execution_params(series_style_id: str) -> dict[str, Any]:
    style_execution = _STYLE_EXECUTION_REGISTRY.get(series_style_id)
    if style_execution is None:
        raise ValueError(
            f"Missing style execution template for series style {series_style_id}"
        )

    missing_keys = [
        key for key in _REQUIRED_STYLE_EXECUTION_KEYS if key not in style_execution
    ]
    if missing_keys:
        raise ValueError(
            "Incomplete style execution template for "
            f"{series_style_id}; missing: {', '.join(missing_keys)}"
        )

    return deepcopy(style_execution)


def _merge_style_execution_override(
    style_execution: dict[str, Any],
    role_execution_override: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged_execution = deepcopy(style_execution)
    if role_execution_override:
        merged_execution.update(deepcopy(role_execution_override))
    return merged_execution


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_freeze(item) for item in value)
    return deepcopy(value)


def _resolve_reference_guided_still_backend_family(
    role_execution_override: Mapping[str, Any] | None,
) -> str | None:
    if not role_execution_override:
        return None

    reference_guided = role_execution_override.get("reference_guided")
    still_backend_family = role_execution_override.get("still_backend_family")

    if reference_guided is None and still_backend_family is None:
        return None
    if reference_guided is not True:
        raise ValueError(
            "Invalid reference-guided role override; expected reference_guided is True"
        )
    if not isinstance(still_backend_family, str) or not still_backend_family.strip():
        raise ValueError(
            "Invalid reference-guided role override; expected a non-empty "
            "still_backend_family"
        )
    return still_backend_family


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
    if panel_type not in role_profile.panel_types:
        raise ValueError(
            f"panel_type {panel_type} is not allowed for role_profile "
            f"{role_profile.profile_id}"
        )

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
        character.face_structure_notes,
        character.eye_signature,
        character.hair_signature,
        character.skin_surface_policy,
        character.body_signature,
        character.expression_range,
        character.identity_negative_rules,
        character.anti_drift,
        character.wardrobe_notes,
        character.personality_notes,
        character.reference_descriptor_notes,
    )
    style_block = (
        f"Series style: {style.display_name}",
        style.line_policy,
        style.shading_policy,
        style.surface_texture_policy,
        style.panel_readability_policy,
        style.artifact_avoidance_policy,
        style.hand_face_reliability_policy,
        f"Style notes: {style.notes}",
    )

    binding_fragments: list[str] = [f"Binding notes: {binding.notes}"]
    binding_fragments.extend(
        [
            f"Identity lock: {binding.identity_lock_strength}",
            f"Hair lock: {binding.hair_lock_strength}",
            f"Face lock: {binding.face_lock_strength}",
            f"Wardrobe family: {binding.allowed_wardrobe_family}",
            f"Do not mutate: {binding.do_not_mutate}",
        ]
    )
    if location_label and location_label.strip():
        binding_fragments.append(f"Location: {location_label.strip()}")
    if continuity_notes and continuity_notes.strip():
        binding_fragments.append(f"Continuity: {continuity_notes.strip()}")
    binding_block = tuple(binding_fragments)

    style_execution = _merge_style_execution_override(
        _resolve_style_execution_params(series_style_id),
        style.role_execution_overrides.get(panel_type),
    )
    reference_guided_backend_family = _resolve_reference_guided_still_backend_family(
        style.role_execution_overrides.get(panel_type)
    )

    # Precedence: style base execution -> style role override -> binding lock strengths -> role constraints.
    execution_params: dict[str, Any] = {
        "checkpoint": style_execution["checkpoint"],
        "loras": style_execution["loras"],
        "steps": style_execution["steps"],
        "cfg": style_execution["cfg"],
        "sampler": style_execution["sampler"],
        "positive_merge_sequence": _POSITIVE_MERGE_SEQUENCE,
        "negative_merge_sequence": _NEGATIVE_MERGE_SEQUENCE,
    }
    execution_params.update(
        _BINDING_EXECUTION_REGISTRY.get(binding_id, _DEFAULT_BINDING_LOCK_STRENGTHS)
    )
    execution_params["width"] = role_profile.width
    execution_params["height"] = role_profile.height
    execution_params["framing_profile"] = role_profile.profile_id

    if (
        panel_type == "establish"
        and binding.reference_sets.get(panel_type)
        and reference_guided_backend_family is not None
    ):
        execution_params["still_backend_family"] = reference_guided_backend_family
        execution_params["reference_guided"] = True

    negative_rules = (
        style.artifact_avoidance_policy,
        character.anti_drift,
        binding.binding_negative_rules,
        f"Role negative: {role_profile.negative_prompt_append}",
    )

    immutable_execution_params = _deep_freeze(execution_params)

    return ComicRenderV2Contract(
        identity_block=identity_block,
        style_block=style_block,
        binding_block=binding_block,
        role_block=role_block,
        execution_params=immutable_execution_params,
        negative_rules=negative_rules,
    )
