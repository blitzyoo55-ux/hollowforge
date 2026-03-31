"""Sequence profile registry for HollowForge orchestration."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

SequenceContentMode = Literal["all_ages", "adult_nsfw"]


class SequenceRegistryError(ValueError):
    """Raised when a profile is unknown or used across the wrong lane."""


_BEAT_GRAMMARS: dict[str, dict[str, Any]] = {
    "stage1_single_location_v1": {
        "id": "stage1_single_location_v1",
        "content_mode": "all_ages",
        "shot_count": 6,
        "beats": [
            "establish",
            "attention",
            "approach",
            "contact_action",
            "close_reaction",
            "settle",
        ],
    },
    "adult_stage1_v1": {
        "id": "adult_stage1_v1",
        "content_mode": "adult_nsfw",
        "shot_count": 6,
        "beats": [
            "establish",
            "attention",
            "approach",
            "contact_action",
            "close_reaction",
            "settle",
        ],
    }
}

_PROMPT_PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "safe_hosted_grok": {
        "id": "safe_hosted_grok",
        "content_mode": "all_ages",
        "provider_kind": "xai",
        "structured_json": True,
        "strict_json": False,
    },
    "safe_openrouter_fallback": {
        "id": "safe_openrouter_fallback",
        "content_mode": "all_ages",
        "provider_kind": "openrouter",
        "structured_json": True,
        "strict_json": False,
    },
    "adult_openrouter_grok": {
        "id": "adult_openrouter_grok",
        "content_mode": "adult_nsfw",
        "provider_kind": "openrouter",
        "structured_json": True,
        "strict_json": False,
    },
    "adult_local_llm": {
        "id": "adult_local_llm",
        "content_mode": "adult_nsfw",
        "provider_kind": "local_llm",
        "structured_json": True,
        "strict_json": False,
    },
    "adult_local_llm_strict_json": {
        "id": "adult_local_llm_strict_json",
        "content_mode": "adult_nsfw",
        "provider_kind": "local_llm",
        "structured_json": True,
        "strict_json": True,
    },
}

_ANIMATION_EXECUTOR_PROFILES: dict[str, dict[str, Any]] = {
    "safe_local_preview": {
        "id": "safe_local_preview",
        "content_mode": "all_ages",
        "executor_mode": "local",
        "execution_lane": "safe",
    },
    "safe_remote_prod": {
        "id": "safe_remote_prod",
        "content_mode": "all_ages",
        "executor_mode": "remote_worker",
        "execution_lane": "safe",
    },
    "adult_local_preview": {
        "id": "adult_local_preview",
        "content_mode": "adult_nsfw",
        "executor_mode": "local",
        "execution_lane": "adult",
    },
    "adult_remote_prod": {
        "id": "adult_remote_prod",
        "content_mode": "adult_nsfw",
        "executor_mode": "remote_worker",
        "execution_lane": "adult",
    },
}


def _clone_profile(
    profiles: dict[str, dict[str, Any]],
    profile_id: str,
    *,
    content_mode: SequenceContentMode | None = None,
    kind: str,
) -> dict[str, Any]:
    profile = profiles.get(profile_id)
    if profile is None:
        raise SequenceRegistryError(f"Unknown {kind} profile: {profile_id}")

    if content_mode is not None and profile.get("content_mode") != content_mode:
        raise SequenceRegistryError(
            f"{kind} profile '{profile_id}' is not valid for content mode '{content_mode}'"
        )

    return deepcopy(profile)


def get_beat_grammar(
    profile_id: str,
    *,
    content_mode: SequenceContentMode | None = None,
) -> dict[str, Any]:
    return _clone_profile(
        _BEAT_GRAMMARS,
        profile_id,
        content_mode=content_mode,
        kind="beat grammar",
    )


def get_prompt_provider_profile(
    profile_id: str,
    *,
    content_mode: SequenceContentMode | None = None,
) -> dict[str, Any]:
    return _clone_profile(
        _PROMPT_PROVIDER_PROFILES,
        profile_id,
        content_mode=content_mode,
        kind="prompt provider",
    )


def get_animation_executor_profile(
    profile_id: str,
    *,
    content_mode: SequenceContentMode | None = None,
) -> dict[str, Any]:
    return _clone_profile(
        _ANIMATION_EXECUTOR_PROFILES,
        profile_id,
        content_mode=content_mode,
        kind="animation executor",
    )
