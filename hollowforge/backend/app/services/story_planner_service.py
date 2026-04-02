"""Deterministic preview planner for Story Planner v1."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from app.config import settings
from app.models import (
    GenerationCreate,
    StoryPlannerCastInput,
    StoryPlannerAnchorQueueResponse,
    StoryPlannerAnchorQueuedShotResponse,
    StoryPlannerAnchorRenderSnapshot,
    StoryPlannerCharacterCatalogEntry,
    StoryPlannerEpisodeBrief,
    StoryPlannerLocationCatalogEntry,
    StoryPlannerPlanRequest,
    StoryPlannerPlanResponse,
    StoryPlannerPreferredAnchorBeat,
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
_STORY_PLANNER_APPROVAL_SECRET_FILENAME = "story_planner_approval_secret.txt"
_STORY_PLANNER_APPROVAL_SECRET_LOCK_FILENAME = "story_planner_approval_secret.lock"
_LEAD_VERB_MARKERS = (
    " meets ",
    " pauses ",
    " compares ",
    " arrives ",
    " enters ",
    " waits ",
    " reads ",
    " finds ",
    " sees ",
    " hears ",
    " follows ",
    " steps ",
    " crosses ",
    " stops ",
    " studies ",
    " checks ",
)
_SUPPORT_CONNECTOR_MARKERS = (
    " meets ",
    " with ",
    " and ",
    " beside ",
    " alongside ",
)
_CLAUSE_STOP_MARKERS = (
    " in ",
    " at ",
    " inside ",
    " near ",
    " after ",
    " before ",
    " while ",
    " during ",
    " as ",
    " when ",
    " because ",
    " under ",
    " by ",
    " on ",
)
_REVEAL_DETAIL_MARKERS = (
    " after ",
    " when ",
    " while ",
    " because ",
    " as ",
)


class StoryPlannerValidationError(ValueError):
    """Planner-specific validation error for user-facing request issues."""


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


def _resolve_story_planner_location(
    *,
    story_prompt: str,
    location_id: str | None,
    locations: list[StoryPlannerLocationCatalogEntry],
) -> tuple[StoryPlannerLocationCatalogEntry, str]:
    if location_id is not None:
        locked_location = next(
            (location for location in locations if location.id == location_id),
            None,
        )
        if locked_location is None:
            raise StoryPlannerValidationError(
                f"location_id '{location_id}' was not found in the catalog."
            )
        return (
            locked_location,
            f"Locked to catalog location: {locked_location.name}.",
        )

    return _resolve_location(story_prompt, locations)


def _normalize_story_prompt(prompt: str) -> str:
    normalized = re.sub(r"\s+", " ", prompt).strip()
    return normalized.rstrip(" .,!?:;")


def _sentence_case(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    return f"{cleaned[0].upper()}{cleaned[1:]}"


def _truncate_at_markers(text: str, markers: tuple[str, ...]) -> str:
    candidate = text
    lowered = text.lower()
    cut_indexes = [lowered.find(marker) for marker in markers if lowered.find(marker) != -1]
    if cut_indexes:
        candidate = text[: min(cut_indexes)]
    return candidate.strip(" ,.;:!-")


def _extract_lead_from_prompt(prompt: str) -> str | None:
    normalized = _normalize_story_prompt(prompt)
    lowered = f" {normalized.lower()} "
    for marker in _LEAD_VERB_MARKERS:
        index = lowered.find(marker)
        if index != -1:
            lead = normalized[: max(0, index - 1)].strip(" ,.;:!-")
            if lead:
                return lead
    return None


def _extract_support_from_prompt(prompt: str, lead_hint: str | None) -> str | None:
    normalized = _normalize_story_prompt(prompt)
    lowered = f" {normalized.lower()} "

    for marker in _SUPPORT_CONNECTOR_MARKERS:
        index = lowered.find(marker)
        if index == -1:
            continue
        start = index + len(marker) - 1
        tail = normalized[start:].strip()
        support = _truncate_at_markers(tail, _CLAUSE_STOP_MARKERS)
        if support and support != lead_hint:
            return support
    return None


def _extract_reveal_detail(prompt: str) -> str:
    normalized = _normalize_story_prompt(prompt)
    lowered = f" {normalized.lower()} "
    for marker in _REVEAL_DETAIL_MARKERS:
        index = lowered.find(marker)
        if index == -1:
            continue
        detail = normalized[index + len(marker) - 1 :].strip()
        detail = _truncate_at_markers(detail, (" and ",))
        if detail:
            return detail
    return normalized


def _has_reveal_detail_hint(prompt: str) -> bool:
    lowered = f" {_normalize_story_prompt(prompt).lower()} "
    return any(marker in lowered for marker in _REVEAL_DETAIL_MARKERS)


def _infer_prompt_cast(
    prompt: str,
) -> list[StoryPlannerResolvedCastEntry]:
    lead_hint = _extract_lead_from_prompt(prompt)
    support_hint = _extract_support_from_prompt(prompt, lead_hint)
    inferred_cast: list[StoryPlannerResolvedCastEntry] = []

    inferred_cast.append(
        StoryPlannerResolvedCastEntry(
            role="lead",
            source_type="freeform",
            freeform_description=lead_hint or "unresolved lead implied by the story prompt",
            resolution_note="Derived lead candidate from the story prompt.",
        )
    )

    if support_hint:
        inferred_cast.append(
            StoryPlannerResolvedCastEntry(
                role="support",
                source_type="freeform",
                freeform_description=support_hint,
                resolution_note="Derived support presence from the story prompt.",
            )
        )

    return inferred_cast


def _merge_prompt_cast(
    prompt: str,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
) -> list[StoryPlannerResolvedCastEntry]:
    if any(member.role == "lead" for member in resolved_cast) and any(
        member.role == "support" for member in resolved_cast
    ):
        return resolved_cast

    inferred_by_role = {
        member.role: member for member in _infer_prompt_cast(prompt)
    }
    merged = list(resolved_cast)

    for role in ("lead", "support"):
        if role in {member.role for member in merged}:
            continue
        inferred = inferred_by_role.get(role)
        if inferred is not None:
            merged.append(inferred)

    role_order = {"lead": 0, "support": 1}
    merged.sort(key=lambda member: role_order.get(member.role, 99))
    return merged


def _normalize_freeform_support_description(description: str | None) -> str:
    if not description:
        return ""
    return re.sub(r"\s+", " ", description).strip(" .,!?:;-")


def _is_sparse_freeform_support_description(description: str | None) -> bool:
    normalized = _normalize_freeform_support_description(description)
    if not normalized:
        return True

    tokens = [token for token in re.findall(r"[a-z0-9]+", normalized.lower()) if token]
    meaningful_tokens = [
        token
        for token in tokens
        if token
        not in {
            "a",
            "an",
            "and",
            "adult",
            "at",
            "by",
            "for",
            "figure",
            "in",
            "is",
            "of",
            "on",
            "person",
            "presence",
            "quiet",
            "secondary",
            "someone",
            "support",
            "the",
            "to",
            "with",
        }
    ]
    return len(meaningful_tokens) < 2


def _build_freeform_support_synthesis(
    *,
    lane: str,
    description: str,
    sparse_description: bool,
    lead_label: str,
) -> dict[str, str]:
    if lane == "adult_nsfw":
        identity_prefix = "Adult secondary figure"
        wardrobe_prefix = "Use subdued adult wardrobe cues"
    else:
        identity_prefix = "Supporting figure"
        wardrobe_prefix = "Use subdued wardrobe cues"

    if sparse_description:
        canonical_anchor = f"{identity_prefix} with a restrained, observant presence."
        wardrobe_notes = (
            f"{wardrobe_prefix} that keep the support figure secondary to the lead."
        )
        personality_notes = "Quiet, observant, and deferential to the lead's space."
    else:
        canonical_anchor = f"{identity_prefix}: {description}."
        wardrobe_notes = (
            f"Keep the look grounded in {description} and visually secondary to the lead."
        )
        personality_notes = (
            f"{_sentence_case(description)} energy, with a restrained secondary presence."
        )
    if lead_label:
        anti_drift = (
            f"Keep the support presence visually separate from {lead_label} by using a smaller, secondary silhouette, different styling, and no lead-like framing."
        )
    else:
        anti_drift = (
            "Keep the support presence visually separate from the lead by using a smaller, secondary silhouette and no lead-like framing."
        )

    return {
        "canonical_anchor": canonical_anchor,
        "anti_drift": anti_drift,
        "wardrobe_notes": wardrobe_notes,
        "personality_notes": personality_notes,
    }


def _synthesize_freeform_support_metadata(
    *,
    lane: str,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
) -> list[StoryPlannerResolvedCastEntry]:
    lead = next((member for member in resolved_cast if member.role == "lead"), None)
    lead_label = _format_story_planner_cast_label(lead) if lead is not None else ""
    synthesized_cast: list[StoryPlannerResolvedCastEntry] = []

    for member in resolved_cast:
        if member.role != "support" or member.source_type != "freeform":
            synthesized_cast.append(member)
            continue

        description = _normalize_freeform_support_description(
            member.freeform_description
        )
        sparse_description = _is_sparse_freeform_support_description(description)
        synthesis = _build_freeform_support_synthesis(
            lane=lane,
            description=description,
            sparse_description=sparse_description,
            lead_label=lead_label,
        )

        synthesized_cast.append(
            member.model_copy(
                update=synthesis
            )
        )

    return synthesized_cast


def _recommend_anchor_shot(
    *,
    lane: str,
    preferred_anchor_beat: StoryPlannerPreferredAnchorBeat,
    story_prompt: str,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    shots: list[StoryPlannerShotCard],
) -> tuple[int, str]:
    valid_shot_numbers = {shot.shot_no for shot in shots}

    if preferred_anchor_beat != "auto":
        preferred_shot_no_by_beat = {
            "exchange": 2,
            "reveal": 3,
            "decision": 4,
        }
        preferred_shot_no = preferred_shot_no_by_beat.get(preferred_anchor_beat)
        if preferred_shot_no is None:
            raise StoryPlannerValidationError(
                f"preferred_anchor_beat '{preferred_anchor_beat}' is not supported."
            )
        reason = f"Preferred anchor beat '{preferred_anchor_beat}' maps to shot {preferred_shot_no}."
        if preferred_shot_no in valid_shot_numbers:
            return preferred_shot_no, reason

    has_lead = any(member.role == "lead" for member in resolved_cast)
    has_support = any(member.role == "support" for member in resolved_cast)

    if lane == "adult_nsfw":
        if has_lead and has_support:
            ranking = [2, 3, 4, 1]
            reason = "Adult NSFW plan with lead and support present favors the exchange shot first."
        elif not has_support and _has_reveal_detail_hint(story_prompt):
            ranking = [3, 4, 2, 1]
            reason = "Adult NSFW plan with a reveal cue and no support cast favors the reveal shot first."
        else:
            ranking = [4, 3, 2, 1]
            reason = "Adult NSFW plan falls back to the decision shot first."
    else:
        ranking = [1, 2, 3, 4]
        reason = "Safe lanes keep the establishing shot first."

    for shot_no in ranking:
        if shot_no in valid_shot_numbers:
            return shot_no, reason

    return shots[0].shot_no, reason


def _story_planner_approval_secret_path() -> Path:
    return settings.DATA_DIR / _STORY_PLANNER_APPROVAL_SECRET_FILENAME


def _story_planner_approval_secret_lock_path() -> Path:
    return settings.DATA_DIR / _STORY_PLANNER_APPROVAL_SECRET_LOCK_FILENAME


def _read_story_planner_approval_secret(secret_path: Path) -> str | None:
    if not secret_path.is_file():
        return None
    secret = secret_path.read_text(encoding="utf-8").strip()
    return secret or None


def _acquire_story_planner_approval_lock(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


@lru_cache(maxsize=1)
def _get_story_planner_approval_secret() -> str:
    configured_secret = settings.ANIMATION_CALLBACK_TOKEN.strip()
    if configured_secret:
        return configured_secret

    secret_path = _story_planner_approval_secret_path()
    lock_path = _story_planner_approval_secret_lock_path()
    persisted_secret = _read_story_planner_approval_secret(secret_path)
    if persisted_secret is not None:
        return persisted_secret

    with _acquire_story_planner_approval_lock(lock_path):
        persisted_secret = _read_story_planner_approval_secret(secret_path)
        if persisted_secret is not None:
            return persisted_secret
        generated_secret = secrets.token_urlsafe(32)
        tmp_path = secret_path.with_name(f"{secret_path.name}.tmp-{os.getpid()}")
        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                handle.write(generated_secret)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, secret_path)
            return generated_secret
        finally:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass


def _story_planner_approval_snapshot(
    plan: StoryPlannerPlanResponse,
) -> dict[str, object]:
    return plan.model_dump(mode="json", exclude={"approval_token"})


def _build_story_planner_approval_token(
    snapshot: dict[str, object],
) -> str:
    canonical_snapshot = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hmac.new(
        _get_story_planner_approval_secret().encode("utf-8"),
        canonical_snapshot.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _validate_story_planner_approval_token(plan: StoryPlannerPlanResponse) -> None:
    if not plan.approval_token.strip():
        raise ValueError("approved_plan approval_token is required")
    expected_token = _build_story_planner_approval_token(
        _story_planner_approval_snapshot(plan)
    )
    if not hmac.compare_digest(plan.approval_token, expected_token):
        raise ValueError(
            "approved_plan approval_token does not match the approved plan snapshot"
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
                canonical_anchor=character.canonical_anchor,
                anti_drift=character.anti_drift,
                wardrobe_notes=character.wardrobe_notes,
                personality_notes=character.personality_notes,
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


def _resolve_story_planner_checkpoint(
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    catalog: list[StoryPlannerCharacterCatalogEntry],
    policy_pack: StoryPlannerPolicyPackCatalogEntry,
) -> str:
    lead = next(
        (
            member
            for member in resolved_cast
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
    lane: str,
    policy_pack: StoryPlannerPolicyPackCatalogEntry,
) -> str | None:
    if lane == "unrestricted" or policy_pack.negative_prompt_mode == "blank":
        return None

    forbidden_defaults = [
        term.strip()
        for term in policy_pack.forbidden_defaults
        if isinstance(term, str) and term.strip()
    ]
    if forbidden_defaults:
        return ", ".join(dict.fromkeys(forbidden_defaults))
    return None


def _build_story_planner_anchor_render_snapshot(
    *,
    lane: str,
    policy_pack: StoryPlannerPolicyPackCatalogEntry,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    characters: list[StoryPlannerCharacterCatalogEntry],
) -> StoryPlannerAnchorRenderSnapshot:
    checkpoint = _resolve_story_planner_checkpoint(
        resolved_cast,
        characters,
        policy_pack,
    )
    workflow_lane = infer_workflow_lane(checkpoint)
    negative_prompt = _resolve_story_planner_negative_prompt(lane, policy_pack)
    preserve_blank_negative_prompt = negative_prompt is None
    return StoryPlannerAnchorRenderSnapshot(
        policy_pack_id=policy_pack.id,
        checkpoint=checkpoint,
        workflow_lane=workflow_lane,
        negative_prompt=negative_prompt,
        preserve_blank_negative_prompt=preserve_blank_negative_prompt,
    )


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


def _compile_story_planner_anchor_intent(
    plan: StoryPlannerPlanResponse,
    shot: StoryPlannerShotCard,
) -> dict[str, str]:
    lead = next((member for member in plan.resolved_cast if member.role == "lead"), None)
    support = next(
        (member for member in plan.resolved_cast if member.role == "support"),
        None,
    )
    lead_label = _format_story_planner_cast_label(lead)
    support_label = _format_story_planner_cast_label(support)
    relationship_label = (
        f"{lead_label} and {support_label}"
        if support is not None
        else lead_label
    )
    visual_rules = "; ".join(plan.location.visual_rules)
    restricted_elements = (
        ", ".join(plan.location.restricted_elements)
        if plan.location.restricted_elements
        else "none"
    )
    return {
        "subject_focus": (
            f"{lead_label} stays the primary subject, with {support_label} secondary."
        ),
        "relationship_signal": (
            f"{relationship_label} should read clearly in {shot.beat.lower()} through {shot.action}"
        ),
        "environment_signal": (
            f"Frame {plan.location.name} from {plan.location.setting_anchor}; visual rules: {visual_rules}; "
            f"restricted elements: {restricted_elements}"
        ),
        "framing_signal": f"{shot.camera} Anchor the composition around {shot.beat.lower()}.",
        "mood_signal": f"{shot.emotion} carried by {shot.action}",
        "continuity_guard": (
            f"{shot.continuity_note} Keep {plan.location.name} and the resolved cast identity stable."
        ),
    }


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
    anchor_intent = _compile_story_planner_anchor_intent(plan, shot)
    lines = [
        "story_planner_anchor render prompt",
        "render_intent:",
        f"- subject_focus: {anchor_intent['subject_focus']}",
        f"- relationship_signal: {anchor_intent['relationship_signal']}",
        f"- environment_signal: {anchor_intent['environment_signal']}",
        f"- framing_signal: {anchor_intent['framing_signal']}",
        f"- mood_signal: {anchor_intent['mood_signal']}",
        f"- continuity_guard: {anchor_intent['continuity_guard']}",
        "context:",
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
        "continuity_metadata:",
        f"- lead_canonical_anchor: {lead.canonical_anchor if lead and lead.canonical_anchor else 'none'}",
        f"- lead_anti_drift: {lead.anti_drift if lead and lead.anti_drift else 'none'}",
        f"- lead_wardrobe_notes: {lead.wardrobe_notes if lead and lead.wardrobe_notes else 'none'}",
        f"- lead_personality_notes: {lead.personality_notes if lead and lead.personality_notes else 'none'}",
        f"- support_canonical_anchor: {support.canonical_anchor if support and support.canonical_anchor else 'none'}",
        f"- support_anti_drift: {support.anti_drift if support and support.anti_drift else 'none'}",
        f"- support_wardrobe_notes: {support.wardrobe_notes if support and support.wardrobe_notes else 'none'}",
        f"- support_personality_notes: {support.personality_notes if support and support.personality_notes else 'none'}",
        f"- location_visual_rules: {'; '.join(plan.location.visual_rules)}",
        f"- location_restricted_elements: {', '.join(plan.location.restricted_elements) if plan.location.restricted_elements else 'none'}",
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


def _build_story_planner_anchor_source_id(
    *,
    plan: StoryPlannerPlanResponse,
    shot: StoryPlannerShotCard,
) -> str:
    digest_payload = {
        "story_prompt": plan.story_prompt,
        "lane": plan.lane,
        "policy_pack_id": plan.policy_pack_id,
        "anchor_render": plan.anchor_render.model_dump(),
        "resolved_cast": [member.model_dump() for member in plan.resolved_cast],
        "location": plan.location.model_dump(),
        "shot": shot.model_dump(),
    }
    digest = hashlib.sha256(
        json.dumps(
            digest_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"story_planner_anchor:{digest}:shot_{shot.shot_no:02d}"


async def queue_story_planner_anchor_batch(
    approved_plan: StoryPlannerPlanResponse,
    generation_service,
    candidate_count: int = 2,
) -> StoryPlannerAnchorQueueResponse:
    _validate_story_planner_approval_token(approved_plan)
    checkpoint = approved_plan.anchor_render.checkpoint
    workflow_lane = approved_plan.anchor_render.workflow_lane
    lane_spec = get_workflow_lane_spec(workflow_lane)
    negative_prompt = approved_plan.anchor_render.negative_prompt
    preserve_blank_negative_prompt = (
        approved_plan.anchor_render.preserve_blank_negative_prompt
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
            preserve_blank_negative_prompt=preserve_blank_negative_prompt,
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
            source_id=_build_story_planner_anchor_source_id(
                plan=approved_plan,
                shot=shot,
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
    story_prompt: str,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    location: StoryPlannerResolvedLocationEntry,
) -> StoryPlannerEpisodeBrief:
    lead_label, support_label = _format_cast_labels(resolved_cast)
    story_focus = _normalize_story_prompt(story_prompt)
    reveal_detail = _extract_reveal_detail(story_prompt)
    return StoryPlannerEpisodeBrief(
        premise=(
            f"At {location.name}, {story_focus}."
        ),
        continuity_guidance=[
            f"Keep {location.name} as the only location and preserve its visual rules.",
            f"Keep {lead_label}'s canon details stable across all shots.",
            f"Keep the support cast secondary while the prompt tension stays anchored on {reveal_detail}.",
        ],
    )


def _build_shots(
    story_prompt: str,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    location: StoryPlannerResolvedLocationEntry,
    lane: str,
) -> list[StoryPlannerShotCard]:
    lead_label, support_label = _format_cast_labels(resolved_cast)
    story_focus = _normalize_story_prompt(story_prompt)
    reveal_detail = _extract_reveal_detail(story_prompt)
    if lane == "adult_nsfw":
        return [
            StoryPlannerShotCard(
                shot_no=1,
                beat="Establish the scene",
                camera=f"Wide establishing shot inside {location.name}.",
                action=_sentence_case(story_focus),
                emotion="Measured alertness",
                continuity_note=f"Hold {location.name}'s visual rules and keep the lead silhouette consistent.",
            ),
            StoryPlannerShotCard(
                shot_no=2,
                beat="Introduce the exchange",
                camera="Medium tracking shot at shoulder height, close enough to read the exchange.",
                action=(
                    f"{lead_label} and {support_label} exchange a quiet gaze in the private space, "
                    f"making the relationship signal readable while the conversation circles {reveal_detail}."
                ),
                emotion="Quietly charged attention",
                continuity_note="Keep their spacing, gaze line, and body language readable inside the same room.",
            ),
            StoryPlannerShotCard(
                shot_no=3,
                beat="Reveal the key detail",
                camera="Over-the-shoulder close-up with intimate framing.",
                action=(
                    f"{lead_label}'s posture and hands reveal the tension around {reveal_detail} while "
                    f"{support_label} stays close in the private space."
                ),
                emotion="Controlled tension",
                continuity_note="Preserve expressive body language and the same location anchor.",
            ),
            StoryPlannerShotCard(
                shot_no=4,
                beat="Close on a decision",
                camera="Tight two-shot with shallow depth of field.",
                action=(
                    f"{lead_label} makes the deciding move after {reveal_detail}, using a small, deliberate gesture."
                ),
                emotion="Controlled resolve",
                continuity_note="End on the same setting anchor and preserve the private-space framing into the next episode.",
            ),
        ]

    return [
        StoryPlannerShotCard(
            shot_no=1,
            beat="Establish the scene",
            camera=f"Wide establishing shot inside {location.name}.",
            action=_sentence_case(story_focus),
            emotion="Measured alertness",
            continuity_note=f"Hold {location.name}'s visual rules and keep the lead silhouette consistent.",
        ),
        StoryPlannerShotCard(
            shot_no=2,
            beat="Introduce the exchange",
            camera="Medium tracking shot at shoulder height.",
            action=(
                f"{support_label} shifts the exchange around {reveal_detail} while "
                f"{lead_label} stays in focus."
            ),
            emotion="Quiet curiosity",
            continuity_note="Keep the support presence secondary and readable.",
        ),
        StoryPlannerShotCard(
            shot_no=3,
            beat="Reveal the key detail",
            camera="Over-the-shoulder close-up.",
            action=f"The key detail comes into focus: {reveal_detail}.",
            emotion="Focused concern",
            continuity_note="Preserve the same wardrobe, lighting, and single-location framing.",
        ),
        StoryPlannerShotCard(
            shot_no=4,
            beat="Close on a decision",
            camera="Tight two-shot with shallow depth of field.",
            action=f"{lead_label} commits to the next move after {reveal_detail}.",
            emotion="Controlled resolve",
            continuity_note="End on the same setting anchor to preserve continuity into the next episode.",
        ),
    ]


def plan_story_episode(request: StoryPlannerPlanRequest) -> StoryPlannerPlanResponse:
    catalog = load_story_planner_catalog()
    location, match_note = _resolve_story_planner_location(
        story_prompt=request.story_prompt,
        location_id=request.location_id,
        locations=catalog.locations,
    )
    resolved_location = StoryPlannerResolvedLocationEntry(
        id=location.id,
        name=location.name,
        setting_anchor=location.setting_anchor,
        visual_rules=location.visual_rules,
        restricted_elements=location.restricted_elements,
        match_note=match_note,
    )
    resolved_cast = [
        _resolve_cast_member(member, catalog.characters) for member in request.cast
    ]
    resolved_cast = _merge_prompt_cast(request.story_prompt, resolved_cast)
    resolved_cast = _synthesize_freeform_support_metadata(
        lane=request.lane,
        resolved_cast=resolved_cast,
    )
    policy_pack = _select_policy_pack(request.lane, catalog.policy_packs)
    shots = _build_shots(
        request.story_prompt,
        resolved_cast,
        resolved_location,
        request.lane,
    )
    recommended_anchor_shot_no, recommended_anchor_reason = _recommend_anchor_shot(
        lane=request.lane,
        preferred_anchor_beat=request.preferred_anchor_beat,
        story_prompt=request.story_prompt,
        resolved_cast=resolved_cast,
        shots=shots,
    )
    anchor_render = _build_story_planner_anchor_render_snapshot(
        lane=request.lane,
        policy_pack=policy_pack,
        resolved_cast=resolved_cast,
        characters=catalog.characters,
    )
    plan_payload = {
        "story_prompt": request.story_prompt,
        "lane": request.lane,
        "policy_pack_id": policy_pack.id,
        "recommended_anchor_shot_no": recommended_anchor_shot_no,
        "recommended_anchor_reason": recommended_anchor_reason,
        "anchor_render": anchor_render.model_dump(mode="json"),
        "resolved_cast": [member.model_dump(mode="json") for member in resolved_cast],
        "location": resolved_location.model_dump(mode="json"),
        "episode_brief": _build_episode_brief(
            request.story_prompt,
            resolved_cast,
            resolved_location,
        ).model_dump(
            mode="json"
        ),
        "shots": [shot.model_dump(mode="json") for shot in shots],
    }
    plan_payload["approval_token"] = _build_story_planner_approval_token(plan_payload)

    return StoryPlannerPlanResponse.model_validate(plan_payload)
