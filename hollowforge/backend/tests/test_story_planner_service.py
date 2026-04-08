from __future__ import annotations
from pathlib import Path

from pydantic import ValidationError
import pytest

from app.models import GenerationResponse, StoryPlannerCastInput, StoryPlannerPlanRequest
from app.services import story_planner_service
from app.services.story_planner_service import (
    _get_story_planner_approval_secret,
    plan_story_episode,
    queue_story_planner_anchor_batch,
)


def _build_request(
    *,
    story_prompt: str,
    lane: str = "adult_nsfw",
) -> StoryPlannerPlanRequest:
    return StoryPlannerPlanRequest(
        story_prompt=story_prompt,
        lane=lane,
        cast=[
            StoryPlannerCastInput(
                role="lead",
                source_type="registry",
                character_id="hana_seo",
            ),
            StoryPlannerCastInput(
                role="support",
                source_type="freeform",
                freeform_description="quiet messenger in a dark coat",
            ),
        ],
    )


def _build_generation_response(generation_id: str, *, prompt: str) -> GenerationResponse:
    return GenerationResponse(
        id=generation_id,
        prompt=prompt,
        checkpoint="waiIllustriousSDXL_v140.safetensors",
        loras=[],
        seed=700,
        steps=28,
        cfg=7.0,
        width=832,
        height=1216,
        sampler="euler",
        scheduler="normal",
        status="queued",
        created_at="2026-03-27T00:00:00+00:00",
    )


class _CapturingGenerationService:
    def __init__(self) -> None:
        self.batch_requests = []

    async def queue_generation_batch(  # type: ignore[no-untyped-def]
        self,
        generation,
        count: int,
        seed_increment: int,
    ):
        self.batch_requests.append((generation, count, seed_increment))
        queued = [
            _build_generation_response(
                f"queued-{len(self.batch_requests)}-{index + 1}",
                prompt=generation.prompt,
            )
            for index in range(count)
        ]
        return 700, queued


def test_plan_story_episode_builds_episode_brief_and_four_shot_plan() -> None:
    preview = plan_story_episode(
        _build_request(
            story_prompt=(
                "Hana Seo meets a quiet messenger in the Moonlit Bathhouse "
                "corridor after closing."
            )
        )
    )

    assert preview.policy_pack_id == "canon_adult_nsfw_v1"
    assert preview.location.match_note
    assert preview.episode_brief.premise
    assert preview.episode_brief.continuity_guidance
    assert preview.anchor_render.policy_pack_id == preview.policy_pack_id
    assert preview.anchor_render.checkpoint == "waiIllustriousSDXL_v140.safetensors"
    assert preview.anchor_render.workflow_lane == "sdxl_illustrious"
    assert (
        preview.anchor_render.negative_prompt
        == "minors, age ambiguity, non-consensual framing"
    )
    assert preview.anchor_render.preserve_blank_negative_prompt is False
    assert preview.approval_token
    assert len(preview.approval_token) == 64
    assert preview.resolved_cast[0].canonical_anchor
    assert preview.resolved_cast[0].anti_drift
    assert preview.resolved_cast[0].wardrobe_notes
    assert preview.resolved_cast[0].personality_notes
    assert preview.location.visual_rules
    assert preview.location.restricted_elements
    assert len(preview.shots) == 4
    assert [shot.shot_no for shot in preview.shots] == [1, 2, 3, 4]
    assert all(shot.beat for shot in preview.shots)
    assert all(shot.camera for shot in preview.shots)
    assert all(shot.action for shot in preview.shots)
    assert all(shot.emotion for shot in preview.shots)
    assert all(shot.continuity_note for shot in preview.shots)


def test_plan_story_episode_resolves_registry_cast_and_preserves_freeform_support() -> None:
    preview = plan_story_episode(
        _build_request(
            story_prompt=(
                "Hana Seo and a quiet messenger compare notes by the service door."
            )
        )
    )

    lead = next(member for member in preview.resolved_cast if member.role == "lead")
    support = next(
        member for member in preview.resolved_cast if member.role == "support"
    )

    assert lead.source_type == "registry"
    assert lead.character_id == "hana_seo"
    assert lead.character_name == "Hana Seo"
    assert support.source_type == "freeform"
    assert support.character_id is None
    assert support.character_name is None
    assert support.freeform_description == "quiet messenger in a dark coat"


def test_plan_story_episode_keeps_unresolved_registry_cast_without_fake_display_name() -> None:
    preview = plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt="An unknown consultant arrives for a private meeting.",
            lane="adult_nsfw",
            cast=[
                StoryPlannerCastInput(
                    role="lead",
                    source_type="registry",
                    character_id="unknown_consultant",
                )
            ],
        )
    )

    lead = preview.resolved_cast[0]

    assert lead.source_type == "registry"
    assert lead.character_id == "unknown_consultant"
    assert lead.character_name is None
    assert "unknown_consultant" in lead.resolution_note
    assert "not found" in lead.resolution_note.lower()


def test_plan_story_episode_derives_prompt_only_cast_from_story_prompt() -> None:
    preview = plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt=(
                "Hana Seo meets a quiet messenger in the Moonlit Bathhouse "
                "corridor after closing."
            ),
            lane="adult_nsfw",
        )
    )

    lead = next(member for member in preview.resolved_cast if member.role == "lead")
    support = next(member for member in preview.resolved_cast if member.role == "support")

    assert lead.source_type == "freeform"
    assert lead.character_id is None
    assert lead.freeform_description is not None
    assert "Hana Seo" in lead.freeform_description
    assert support.source_type == "freeform"
    assert support.freeform_description is not None
    assert "messenger" in support.freeform_description.lower()


def test_plan_story_episode_uses_story_prompt_details_in_brief_and_shots() -> None:
    preview = plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt=(
                "Hana Seo pauses in the Moonlit Bathhouse corridor after reading "
                "a cryptic message."
            ),
            lane="adult_nsfw",
            cast=[
                StoryPlannerCastInput(
                    role="lead",
                    source_type="registry",
                    character_id="hana_seo",
                )
            ],
        )
    )

    assert "cryptic message" in preview.episode_brief.premise.lower()
    assert "cryptic message" in preview.shots[0].action.lower()
    assert "cryptic message" in preview.shots[2].action.lower()


@pytest.mark.asyncio
async def test_queue_story_planner_anchor_batch_includes_continuity_details_in_anchor_prompt() -> None:
    approved_plan = plan_story_episode(
        _build_request(
            story_prompt=(
                "Hana Seo compares notes with a quiet messenger in the Moonlit Bathhouse corridor after closing."
            )
        )
    )
    service = _CapturingGenerationService()

    await queue_story_planner_anchor_batch(approved_plan, service, candidate_count=2)

    first_request = service.batch_requests[0][0]
    assert "canonical_anchor" in first_request.prompt
    assert "Adult Korean woman, luxury skincare strategist" in first_request.prompt
    assert "anti_drift" in first_request.prompt
    assert "wardrobe_notes" in first_request.prompt
    assert "personality_notes" in first_request.prompt
    assert "location_visual_rules" in first_request.prompt
    assert (
        "Preserve premium spa materials such as stone, wood, steam-softened light, and muted reflective surfaces."
        in first_request.prompt
    )
    assert "location_restricted_elements" in first_request.prompt
    assert "neon club lighting" in first_request.prompt


@pytest.mark.asyncio
async def test_queue_story_planner_anchor_batch_rejects_tampered_approved_plan_with_stale_token() -> None:
    approved_plan = plan_story_episode(
        _build_request(
            story_prompt=(
                "Hana Seo compares notes with a quiet messenger in the Moonlit Bathhouse corridor after closing."
            )
        )
    )
    payload = approved_plan.model_dump()
    payload["story_prompt"] = "Hana Seo compares notes in a different corridor after closing."
    tampered_plan = type(approved_plan).model_validate(payload)

    with pytest.raises(ValueError, match="approval_token"):
        await queue_story_planner_anchor_batch(
            tampered_plan,
            _CapturingGenerationService(),
            candidate_count=2,
        )


def test_story_planner_approval_secret_falls_back_to_persisted_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(story_planner_service.settings, "ANIMATION_CALLBACK_TOKEN", "")
    monkeypatch.setattr(story_planner_service.settings, "DATA_DIR", tmp_path)
    _get_story_planner_approval_secret.cache_clear()

    token_calls: list[int] = []

    def fake_token_urlsafe(size: int) -> str:
        token_calls.append(size)
        return "persisted-secret-token"

    monkeypatch.setattr(story_planner_service.secrets, "token_urlsafe", fake_token_urlsafe)

    first_secret = _get_story_planner_approval_secret()
    _get_story_planner_approval_secret.cache_clear()
    second_secret = _get_story_planner_approval_secret()

    secret_path = tmp_path / "story_planner_approval_secret.txt"

    assert first_secret == "persisted-secret-token"
    assert second_secret == "persisted-secret-token"
    assert token_calls == [32]
    assert secret_path.read_text(encoding="utf-8").strip() == "persisted-secret-token"


def test_story_planner_approval_secret_waits_for_existing_file_to_become_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(story_planner_service.settings, "ANIMATION_CALLBACK_TOKEN", "")
    monkeypatch.setattr(story_planner_service.settings, "DATA_DIR", tmp_path)
    _get_story_planner_approval_secret.cache_clear()

    secret_path = tmp_path / "story_planner_approval_secret.txt"
    class _LockHandle:
        def __enter__(self):
            secret_path.write_text("persisted-secret-token", encoding="utf-8")
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(
        story_planner_service,
        "_acquire_story_planner_approval_lock",
        lambda _: _LockHandle(),
    )

    secret = _get_story_planner_approval_secret()

    assert secret == "persisted-secret-token"


def test_story_planner_approval_secret_ignores_leftover_unlocked_lock_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(story_planner_service.settings, "ANIMATION_CALLBACK_TOKEN", "")
    monkeypatch.setattr(story_planner_service.settings, "DATA_DIR", tmp_path)
    _get_story_planner_approval_secret.cache_clear()

    lock_path = tmp_path / "story_planner_approval_secret.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("leftover-lock-file", encoding="utf-8")
    monkeypatch.setattr(
        story_planner_service.secrets,
        "token_urlsafe",
        lambda _: "recovered-secret-token",
    )

    secret = _get_story_planner_approval_secret()
    secret_path = tmp_path / "story_planner_approval_secret.txt"

    assert secret == "recovered-secret-token"
    assert secret_path.read_text(encoding="utf-8").strip() == "recovered-secret-token"
    assert lock_path.exists()


def test_plan_story_episode_resolves_location_from_prompt_and_falls_back_when_needed() -> None:
    matched_preview = plan_story_episode(
        _build_request(
            story_prompt=(
                "The pair trade signals in the rooftop tea lounge above the bathhouse."
            )
        )
    )
    restricted_term_preview = plan_story_episode(
        _build_request(
            story_prompt="A plain studio room with no dance floor staging anywhere.",
        )
    )
    fallback_preview = plan_story_episode(
        _build_request(
            story_prompt="A plain studio room with no clear setting cues.",
        )
    )

    assert matched_preview.location.id == "rooftop_tea_lounge"
    assert "matched" in matched_preview.location.match_note.lower()
    assert restricted_term_preview.location.id == "moonlit_bathhouse"
    assert "fallback" in restricted_term_preview.location.match_note.lower()
    assert fallback_preview.location.id == "moonlit_bathhouse"
    assert fallback_preview.location.match_note
    assert "fallback" in fallback_preview.location.match_note.lower()


def test_plan_story_episode_freezes_blank_negative_prompt_for_unrestricted_lane() -> None:
    preview = plan_story_episode(
        _build_request(
            story_prompt="Hana Seo waits in the bathhouse foyer before dawn.",
            lane="unrestricted",
        )
    )

    assert preview.policy_pack_id == "canon_unrestricted_v1"
    assert preview.anchor_render.policy_pack_id == "canon_unrestricted_v1"
    assert preview.anchor_render.negative_prompt is None
    assert preview.anchor_render.preserve_blank_negative_prompt is True
    assert preview.anchor_render.workflow_lane == "sdxl_illustrious"


def test_story_planner_plan_response_rejects_edited_anchor_render_snapshot() -> None:
    preview = plan_story_episode(
        _build_request(
            story_prompt="Hana Seo waits in the bathhouse foyer before dawn.",
        )
    )
    payload = preview.model_dump()
    payload["anchor_render"]["policy_pack_id"] = "canon_all_ages_v1"

    with pytest.raises(ValidationError, match="anchor_render.policy_pack_id"):
        type(preview).model_validate(payload)


def test_story_planner_plan_response_rejects_noncanonical_shot_numbers() -> None:
    preview = plan_story_episode(
        _build_request(
            story_prompt="Hana Seo waits in the bathhouse foyer before dawn.",
        )
    )
    payload = preview.model_dump()
    payload["shots"][1]["shot_no"] = 1

    with pytest.raises(ValidationError, match="shots must use canonical shot numbers"):
        type(preview).model_validate(payload)
