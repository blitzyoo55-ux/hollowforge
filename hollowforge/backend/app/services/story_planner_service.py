"""Deterministic preview planner for Story Planner v1."""

from __future__ import annotations

import re
from typing import Iterable

from app.config import settings
from app.models import (
    GenerationCreate,
    StoryPlannerCastInput,
    StoryPlannerAnchorQueueResponse,
    StoryPlannerAnchorQueuedShotResponse,
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
from app.services.workflow_registry import get_workflow_lane_spec, infer_workflow_lane


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


def _select_policy_pack_for_plan(
    plan: StoryPlannerPlanResponse,
    packs: list[StoryPlannerPolicyPackCatalogEntry],
) -> StoryPlannerPolicyPackCatalogEntry:
    for pack in packs:
        if pack.id == plan.policy_pack_id:
            return pack
    return _select_policy_pack(plan.lane, packs)


def _resolve_story_planner_checkpoint(
    plan: StoryPlannerPlanResponse,
    catalog: list[StoryPlannerCharacterCatalogEntry],
    policy_pack: StoryPlannerPolicyPackCatalogEntry,
) -> str:
    lead = next(
        (
            member
            for member in plan.resolved_cast
            if member.role == "lead"
            and member.source_type == "registry"
            and member.character_id
        ),
        None,
    )
    if lead is not None:
        character = next(
            (entry for entry in catalog if entry.id == lead.character_id),
            None,
        )
        if character is not None and character.preferred_checkpoints:
            checkpoint = character.preferred_checkpoints[0].strip()
            if checkpoint:
                return checkpoint

    default_checkpoint = str(
        policy_pack.render_preferences.get("default_checkpoint", "")
    ).strip()
    if default_checkpoint:
        return default_checkpoint

    return "waiIllustriousSDXL_v140.safetensors"


def _resolve_story_planner_negative_prompt(
    plan: StoryPlannerPlanResponse,
    policy_pack: StoryPlannerPolicyPackCatalogEntry,
) -> str | None:
    if plan.lane == "unrestricted" or policy_pack.negative_prompt_mode == "blank":
        return None

    forbidden_defaults = [
        term.strip()
        for term in policy_pack.forbidden_defaults
        if isinstance(term, str) and term.strip()
    ]
    if forbidden_defaults:
        return ", ".join(dict.fromkeys(forbidden_defaults))
    return settings.DEFAULT_NEGATIVE_PROMPT


def _format_story_planner_cast_label(member: StoryPlannerResolvedCastEntry | None) -> str:
    if member is None:
        return "unassigned"
    if member.character_name:
        return member.character_name
    if member.character_id:
        return member.character_id
    if member.freeform_description:
        return member.freeform_description
    return member.role


def _build_story_planner_anchor_prompt(
    *,
    plan: StoryPlannerPlanResponse,
    shot: StoryPlannerShotCard,
    checkpoint: str,
    workflow_lane: str,
) -> str:
    lead = next((member for member in plan.resolved_cast if member.role == "lead"), None)
    support = next(
        (member for member in plan.resolved_cast if member.role == "support"),
        None,
    )
    lines = [
        "story_planner_anchor still generation",
        f"story_prompt: {plan.story_prompt}",
        f"lane: {plan.lane}",
        f"policy_pack: {plan.policy_pack_id}",
        f"shot_no: {shot.shot_no}",
        f"episode_premise: {plan.episode_brief.premise}",
        f"location_name: {plan.location.name}",
        f"location_anchor: {plan.location.setting_anchor}",
        "resolved_cast:",
        f"- lead: {_format_story_planner_cast_label(lead)}",
        f"- support: {_format_story_planner_cast_label(support)}",
        "shot_card:",
        f"- beat: {shot.beat}",
        f"- camera: {shot.camera}",
        f"- action: {shot.action}",
        f"- emotion: {shot.emotion}",
        f"- continuity: {shot.continuity_note}",
        "render_goal: preserve character identity, location continuity, and shot composition while producing a single anchor still.",
        f"checkpoint: {checkpoint}",
        f"workflow_lane: {workflow_lane}",
    ]
    return "\n".join(lines)


def _build_story_planner_anchor_tags(
    *,
    plan: StoryPlannerPlanResponse,
    shot_no: int,
) -> list[str]:
    return [
        "story_planner",
        "story_planner_anchor",
        f"lane:{plan.lane}",
        f"policy_pack:{plan.policy_pack_id}",
        f"shot:{shot_no:02d}",
        f"shot_{shot_no:02d}",
        f"location:{plan.location.id}",
    ]


async def queue_story_planner_anchor_batch(
    approved_plan: StoryPlannerPlanResponse,
    generation_service,
    candidate_count: int = 2,
) -> StoryPlannerAnchorQueueResponse:
    catalog = load_story_planner_catalog()
    policy_pack = _select_policy_pack_for_plan(approved_plan, catalog.policy_packs)
    checkpoint = _resolve_story_planner_checkpoint(
        approved_plan,
        catalog.characters,
        policy_pack,
    )
    workflow_lane = infer_workflow_lane(checkpoint)
    lane_spec = get_workflow_lane_spec(workflow_lane)
    negative_prompt = _resolve_story_planner_negative_prompt(
        approved_plan,
        policy_pack,
    )

    queued_generations = []
    queued_shots = []
    for shot in approved_plan.shots:
        generation = GenerationCreate(
            prompt=_build_story_planner_anchor_prompt(
                plan=approved_plan,
                shot=shot,
                checkpoint=checkpoint,
                workflow_lane=workflow_lane,
            ),
            negative_prompt=negative_prompt,
            checkpoint=checkpoint,
            workflow_lane=workflow_lane,
            steps=int(lane_spec.defaults.get("steps", 28)),
            cfg=float(lane_spec.defaults.get("cfg", 7.0)),
            width=int(lane_spec.defaults.get("width", 832)),
            height=int(lane_spec.defaults.get("height", 1216)),
            sampler=str(lane_spec.defaults.get("sampler", "euler")),
            scheduler=str(lane_spec.defaults.get("scheduler", "normal")),
            clip_skip=lane_spec.defaults.get("clip_skip"),
            tags=_build_story_planner_anchor_tags(
                plan=approved_plan,
                shot_no=shot.shot_no,
            ),
            notes=(
                f"story_planner_anchor lane={approved_plan.lane} "
                f"policy_pack={approved_plan.policy_pack_id} "
                f"shot_{shot.shot_no:02d} candidates={candidate_count}"
            ),
            source_id=(
                f"story_planner_anchor:{approved_plan.policy_pack_id}:"
                f"shot_{shot.shot_no:02d}"
            ),
        )
        _, shot_generations = await generation_service.queue_generation_batch(
            generation,
            count=candidate_count,
            seed_increment=1,
        )
        queued_generations.extend(shot_generations)
        queued_shots.append(
            StoryPlannerAnchorQueuedShotResponse(
                shot_no=shot.shot_no,
                generation_ids=[generation.id for generation in shot_generations],
            )
        )

    return StoryPlannerAnchorQueueResponse(
        lane=approved_plan.lane,
        requested_shot_count=len(approved_plan.shots),
        queued_generation_count=len(queued_generations),
        queued_shots=queued_shots,
        queued_generations=queued_generations,
    )


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
