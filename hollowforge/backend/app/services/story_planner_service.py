"""Deterministic preview planner for Story Planner v1."""

from __future__ import annotations

import re
from typing import Iterable

from app.models import (
    StoryPlannerCastInput,
    StoryPlannerCharacterCatalogEntry,
    StoryPlannerEpisodeBrief,
    StoryPlannerLocationCatalogEntry,
    StoryPlannerPlanRequest,
    StoryPlannerPlanResponse,
    StoryPlannerPolicyPackCatalogEntry,
    StoryPlannerResolvedCastEntry,
    StoryPlannerResolvedLocationEntry,
    StoryPlannerShotCard,
)
from app.services.story_planner_catalog import load_story_planner_catalog


_LOCATION_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "before",
    "by",
    "clear",
    "cues",
    "details",
    "during",
    "for",
    "from",
    "in",
    "inside",
    "is",
    "it",
    "keep",
    "no",
    "of",
    "on",
    "over",
    "plain",
    "room",
    "rooms",
    "scene",
    "setting",
    "space",
    "studio",
    "the",
    "to",
    "use",
    "with",
}


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token}


def _location_score(prompt_tokens: set[str], location: StoryPlannerLocationCatalogEntry) -> int:
    fields: Iterable[str] = (
        location.id.replace("_", " "),
        location.name,
        location.setting_anchor,
        " ".join(location.visual_rules),
        " ".join(location.restricted_elements),
    )
    location_tokens = {
        token
        for token in set().union(*(_tokenize(field) for field in fields))
        if token not in _LOCATION_STOPWORDS
    }
    return len(prompt_tokens & location_tokens)


def _resolve_location(
    prompt: str,
    locations: list[StoryPlannerLocationCatalogEntry],
) -> tuple[StoryPlannerLocationCatalogEntry, str]:
    prompt_tokens = _tokenize(prompt)
    ranked = [
        (index, _location_score(prompt_tokens, location), location)
        for index, location in enumerate(locations)
    ]
    ranked.sort(key=lambda item: (-item[1], item[0]))

    _, best_score, best_location = ranked[0]
    if best_score > 0:
        return (
            best_location,
            f"Matched prompt keywords to {best_location.name}.",
        )

    fallback_location = locations[0]
    return (
        fallback_location,
        f"No location match found; fallback to {fallback_location.name}.",
    )


def _resolve_registry_character(
    character_id: str,
    characters: list[StoryPlannerCharacterCatalogEntry],
) -> StoryPlannerCharacterCatalogEntry | None:
    for character in characters:
        if character.id == character_id:
            return character
    return None


def _resolve_cast_member(
    member: StoryPlannerCastInput,
    characters: list[StoryPlannerCharacterCatalogEntry],
) -> StoryPlannerResolvedCastEntry:
    if member.source_type == "registry":
        character = _resolve_registry_character(member.character_id or "", characters)
        if character is not None:
            return StoryPlannerResolvedCastEntry(
                role=member.role,
                source_type=member.source_type,
                character_id=character.id,
                character_name=character.name,
                resolution_note=f"Resolved registry character '{character.id}' from catalog.",
            )
        return StoryPlannerResolvedCastEntry(
            role=member.role,
            source_type=member.source_type,
            character_id=member.character_id,
            character_name=member.character_id,
            resolution_note=(
                f"Registry character '{member.character_id}' was not found in the catalog."
            ),
        )

    return StoryPlannerResolvedCastEntry(
        role=member.role,
        source_type=member.source_type,
        freeform_description=member.freeform_description,
        resolution_note="Kept as freeform support cast for later casting.",
    )


def _select_policy_pack(
    lane: str,
    packs: list[StoryPlannerPolicyPackCatalogEntry],
) -> StoryPlannerPolicyPackCatalogEntry:
    for pack in packs:
        if pack.lane == lane:
            return pack
    return packs[0]


def _format_cast_labels(resolved_cast: list[StoryPlannerResolvedCastEntry]) -> tuple[str, str]:
    lead = next((member for member in resolved_cast if member.role == "lead"), None)
    support = next((member for member in resolved_cast if member.role == "support"), None)

    lead_label = lead.character_name if lead and lead.character_name else "the lead"
    if support is None:
        support_label = "a support presence"
    elif support.character_name:
        support_label = support.character_name
    else:
        support_label = support.freeform_description or "a support presence"

    return lead_label, support_label


def _build_episode_brief(
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    location: StoryPlannerResolvedLocationEntry,
) -> StoryPlannerEpisodeBrief:
    lead_label, support_label = _format_cast_labels(resolved_cast)
    return StoryPlannerEpisodeBrief(
        premise=(
            f"At {location.name}, {lead_label} and {support_label} work through "
            f"the prompt's central tension in a single, contained scene."
        ),
        continuity_guidance=[
            f"Keep {location.name} as the only location and preserve its visual rules.",
            f"Keep {lead_label}'s canon details stable across all shots.",
            "Keep the support cast secondary and unresolved if freeform.",
        ],
    )


def _build_shots(
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    location: StoryPlannerResolvedLocationEntry,
) -> list[StoryPlannerShotCard]:
    lead_label, support_label = _format_cast_labels(resolved_cast)
    return [
        StoryPlannerShotCard(
            shot_no=1,
            beat="Establish the scene",
            camera=f"Wide establishing shot inside {location.name}.",
            action=f"{lead_label} enters and takes in the room before anyone speaks.",
            emotion="Measured alertness",
            continuity_note=f"Hold {location.name}'s visual rules and keep the lead silhouette consistent.",
        ),
        StoryPlannerShotCard(
            shot_no=2,
            beat="Introduce the exchange",
            camera="Medium tracking shot at shoulder height.",
            action=f"{support_label} meets {lead_label} and the first cue is exchanged.",
            emotion="Quiet curiosity",
            continuity_note="Keep the support presence secondary and readable.",
        ),
        StoryPlannerShotCard(
            shot_no=3,
            beat="Reveal the key detail",
            camera="Over-the-shoulder close-up.",
            action="A message, gesture, or object shifts the scene's stakes.",
            emotion="Focused concern",
            continuity_note="Preserve the same wardrobe, lighting, and single-location framing.",
        ),
        StoryPlannerShotCard(
            shot_no=4,
            beat="Close on a decision",
            camera="Tight two-shot with shallow depth of field.",
            action=f"{lead_label} commits to the next move while the support beat lingers.",
            emotion="Controlled resolve",
            continuity_note="End on the same setting anchor to preserve continuity into the next episode.",
        ),
    ]


def plan_story_episode(request: StoryPlannerPlanRequest) -> StoryPlannerPlanResponse:
    catalog = load_story_planner_catalog()
    location, match_note = _resolve_location(request.story_prompt, catalog.locations)
    resolved_location = StoryPlannerResolvedLocationEntry(
        id=location.id,
        name=location.name,
        setting_anchor=location.setting_anchor,
        match_note=match_note,
    )
    resolved_cast = [
        _resolve_cast_member(member, catalog.characters) for member in request.cast
    ]
    policy_pack = _select_policy_pack(request.lane, catalog.policy_packs)

    return StoryPlannerPlanResponse(
        story_prompt=request.story_prompt,
        lane=request.lane,
        policy_pack_id=policy_pack.id,
        resolved_cast=resolved_cast,
        location=resolved_location,
        episode_brief=_build_episode_brief(resolved_cast, resolved_location),
        shots=_build_shots(resolved_cast, resolved_location),
    )
