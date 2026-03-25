"""Sequence run orchestration for HollowForge Stage 1 slices."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol

from app.config import settings
from app.db import get_db
from app.models import GenerationCreate, SequenceRunCreate, SequenceShotCreate
from app.services.generation_service import GenerationService
from app.services.prompt_factory_service import load_prompt_benchmark_snapshot
from app.services.rough_cut_service import build_rough_cut_timeline
from app.services.sequence_blueprint_service import expand_blueprint_into_shots
from app.services.sequence_registry import (
    get_animation_executor_profile,
    get_prompt_provider_profile,
)
from app.services.sequence_repository import (
    create_anchor_candidate,
    create_run,
    get_blueprint,
    insert_shots,
    save_shot_clip,
    update_run_status,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _GenerationBatchQueue(Protocol):
    async def queue_generation_batch(
        self,
        gen: GenerationCreate,
        count: int,
        seed_increment: int = 1,
    ) -> tuple[int, list[Any]]: ...


def _float_score(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _compute_rank_score(candidate: Mapping[str, Any]) -> float:
    explicit_rank = _float_score(candidate.get("rank_score"))
    if explicit_rank is not None:
        return round(explicit_rank, 6)

    metrics = [
        _float_score(candidate.get("identity_score")),
        _float_score(candidate.get("location_lock_score")),
        _float_score(candidate.get("beat_fit_score")),
        _float_score(candidate.get("quality_score")),
    ]
    present = [metric for metric in metrics if metric is not None]
    if not present:
        return 0.0
    return round(sum(present) / len(present), 6)


def select_anchor_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    backup_count: int = 2,
) -> dict[str, Any]:
    """Rank candidates and mark one primary plus N backups."""
    ranked = []
    for candidate in candidates:
        normalized = dict(candidate)
        normalized["rank_score"] = _compute_rank_score(candidate)
        normalized["is_selected_primary"] = False
        normalized["is_selected_backup"] = False
        ranked.append(normalized)

    ranked.sort(
        key=lambda row: (
            -float(row["rank_score"]),
            str(row.get("generation_id") or row.get("id") or ""),
        )
    )

    primary = ranked[0] if ranked else None
    backups = ranked[1 : 1 + max(backup_count, 0)]

    if primary is not None:
        primary["is_selected_primary"] = True
    for row in backups:
        row["is_selected_backup"] = True
    return {
        "primary": primary,
        "backups": backups,
        "ranked": ranked,
    }


def _default_prompt_provider_profile_id(content_mode: str) -> str:
    if content_mode == "adult_nsfw":
        return settings.HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE
    return settings.HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE


def build_shot_prompt_packet(
    blueprint: Mapping[str, Any],
    shot: Mapping[str, Any],
    *,
    prompt_provider_profile_id: str,
    benchmark: Mapping[str, Any],
) -> dict[str, Any]:
    concept_brief = (
        f"Shot {shot['shot_no']} for a {blueprint['target_duration_sec']} second sequence. "
        f"Character: {blueprint['character_id']}. "
        f"Location: {blueprint['location_id']}. "
        f"Beat: {shot['beat_type']}."
    )
    creative_parts = [
        f"camera {shot['camera_intent']}",
        f"emotion {shot['emotion_intent']}",
        f"action {shot['action_intent']}",
    ]
    if blueprint.get("tone"):
        creative_parts.append(f"tone {blueprint['tone']}")
    if shot.get("continuity_rules"):
        creative_parts.append(str(shot["continuity_rules"]))

    prompt = (
        "cinematic continuity still, "
        f"{blueprint['character_id']}, "
        f"{blueprint['location_id']}, "
        + ", ".join(creative_parts)
    )
    return {
        "concept_brief": concept_brief,
        "creative_brief": " | ".join(creative_parts),
        "prompt_provider_profile_id": prompt_provider_profile_id,
        "prompt": prompt,
        "negative_prompt": benchmark.get("negative_prompt"),
        "checkpoint": (benchmark.get("top_checkpoints") or [""])[0],
        "workflow_lane": benchmark.get("workflow_lane"),
        "sampler": benchmark.get("sampler") or "euler",
        "scheduler": benchmark.get("scheduler") or "normal",
        "clip_skip": benchmark.get("clip_skip"),
        "steps": int((benchmark.get("steps_values") or [28])[0]),
        "cfg": float((benchmark.get("cfg_values") or [7.0])[0]),
        "width": int(benchmark.get("width") or 832),
        "height": int(benchmark.get("height") or 1216),
    }


def _generation_request_from_packet(
    packet: Mapping[str, Any],
    *,
    run_id: str,
    shot_id: str,
    shot_no: int,
) -> GenerationCreate:
    notes = json.dumps(
        {
            "sequence": {
                "sequence_run_id": run_id,
                "sequence_shot_id": shot_id,
                "shot_no": shot_no,
            },
            "concept_brief": packet["concept_brief"],
            "creative_brief": packet["creative_brief"],
        },
        ensure_ascii=False,
    )
    return GenerationCreate(
        prompt=str(packet["prompt"]),
        negative_prompt=packet.get("negative_prompt"),
        checkpoint=str(packet["checkpoint"]),
        workflow_lane=packet.get("workflow_lane"),
        steps=int(packet["steps"]),
        cfg=float(packet["cfg"]),
        width=int(packet["width"]),
        height=int(packet["height"]),
        sampler=str(packet["sampler"]),
        scheduler=str(packet["scheduler"]),
        clip_skip=packet.get("clip_skip"),
        notes=notes,
        source_id=shot_id,
    )


def _planned_candidate_scores(index: int, total: int) -> dict[str, float]:
    if total < 1:
        total = 1
    drop = index * 0.04
    return {
        "identity_score": round(max(0.0, 0.98 - drop), 6),
        "location_lock_score": round(max(0.0, 0.95 - drop), 6),
        "beat_fit_score": round(max(0.0, 0.93 - drop), 6),
        "quality_score": round(max(0.0, 0.90 - drop), 6),
    }


async def _create_animation_job(
    *,
    candidate_id: str,
    generation_id: str,
    target_tool: str,
    executor_profile_id: str,
    executor_mode: str,
    sequence_run_id: str,
    sequence_shot_id: str,
    content_mode: str,
    rank_score: float,
) -> dict[str, Any]:
    now = _now_iso()
    job_id = str(uuid.uuid4())
    request_payload = {
        "sequence": {
            "sequence_run_id": sequence_run_id,
            "sequence_shot_id": sequence_shot_id,
            "content_mode": content_mode,
            "executor_profile_id": executor_profile_id,
        },
        "rank_score": rank_score,
    }
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO animation_jobs (
                id,
                candidate_id,
                generation_id,
                publish_job_id,
                target_tool,
                executor_mode,
                executor_key,
                status,
                request_json,
                external_job_id,
                external_job_url,
                output_path,
                error_message,
                submitted_at,
                completed_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (
                job_id,
                candidate_id,
                generation_id,
                target_tool,
                executor_mode,
                executor_profile_id,
                "queued",
                json.dumps(request_payload, ensure_ascii=False),
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM animation_jobs WHERE id = ?",
            (job_id,),
        )
        row = await cursor.fetchone()
    return dict(row or {})


class SequenceRunService:
    """Create a sequence run and seed its Stage 1 orchestration records."""

    def __init__(self, generation_service: GenerationService | _GenerationBatchQueue) -> None:
        self._generation_service = generation_service

    async def create_run_from_blueprint(
        self,
        *,
        blueprint_id: str,
        prompt_provider_profile_id: str | None = None,
        candidate_count: int = 4,
        target_tool: str | None = None,
    ) -> dict[str, Any]:
        if candidate_count < 2:
            raise ValueError("candidate_count must be >= 2")

        blueprint = await get_blueprint(blueprint_id)
        if blueprint is None:
            raise ValueError(f"Unknown sequence blueprint: {blueprint_id}")

        content_mode = str(blueprint.content_mode)
        prompt_profile_id = prompt_provider_profile_id or _default_prompt_provider_profile_id(
            content_mode
        )
        get_prompt_provider_profile(prompt_profile_id, content_mode=blueprint.content_mode)
        executor_profile = get_animation_executor_profile(
            blueprint.executor_policy,
            content_mode=blueprint.content_mode,
        )

        run = await create_run(
            SequenceRunCreate(
                sequence_blueprint_id=blueprint.id,
                content_mode=blueprint.content_mode,
                policy_profile_id=blueprint.policy_profile_id,
                prompt_provider_profile_id=prompt_profile_id,
                execution_mode=str(executor_profile["executor_mode"]),
                status="planning",
            )
        )

        planned_shots = expand_blueprint_into_shots(
            beat_grammar_id=blueprint.beat_grammar_id,
            target_duration_sec=blueprint.target_duration_sec,
            shot_count=blueprint.shot_count,
            content_mode=blueprint.content_mode,
        )
        shots = await insert_shots(
            [
                SequenceShotCreate(
                    sequence_run_id=run.id,
                    content_mode=blueprint.content_mode,
                    policy_profile_id=blueprint.policy_profile_id,
                    shot_no=int(shot["shot_no"]),
                    beat_type=str(shot["beat_type"]),
                    camera_intent=str(shot["camera_intent"]),
                    emotion_intent=str(shot["emotion_intent"]),
                    action_intent=str(shot["action_intent"]),
                    target_duration_sec=int(shot["target_duration_sec"]),
                    continuity_rules=str(shot["continuity_rules"])
                    if shot.get("continuity_rules") is not None
                    else None,
                )
                for shot in planned_shots
            ]
        )

        benchmark = (
            await load_prompt_benchmark_snapshot("auto")
        ).model_dump()
        shot_results: list[dict[str, Any]] = []
        for shot in shots:
            packet = build_shot_prompt_packet(
                blueprint.model_dump(),
                shot.model_dump(),
                prompt_provider_profile_id=prompt_profile_id,
                benchmark=benchmark,
            )
            generation_request = _generation_request_from_packet(
                packet,
                run_id=run.id,
                shot_id=shot.id,
                shot_no=shot.shot_no,
            )
            _, generations = await self._generation_service.queue_generation_batch(
                generation_request,
                count=candidate_count,
            )

            planned_candidates = []
            for index, generation in enumerate(generations):
                candidate = {
                    "generation_id": generation.id,
                    **_planned_candidate_scores(index, len(generations)),
                }
                planned_candidates.append(candidate)

            selected_candidates = select_anchor_candidates(planned_candidates)
            persisted_candidates = []
            animation_jobs = []
            for retry_count, candidate in enumerate(selected_candidates["ranked"]):
                persisted = await create_anchor_candidate(
                    sequence_shot_id=shot.id,
                    content_mode=content_mode,
                    policy_profile_id=blueprint.policy_profile_id,
                    generation_id=str(candidate["generation_id"]),
                    identity_score=float(candidate["identity_score"]),
                    location_lock_score=float(candidate["location_lock_score"]),
                    beat_fit_score=float(candidate["beat_fit_score"]),
                    quality_score=float(candidate["quality_score"]),
                    is_selected_primary=bool(candidate["is_selected_primary"]),
                    is_selected_backup=bool(candidate["is_selected_backup"]),
                )
                persisted["rank_score"] = float(candidate["rank_score"])
                persisted_candidates.append(persisted)

                if not (candidate["is_selected_primary"] or candidate["is_selected_backup"]):
                    continue
                job = await _create_animation_job(
                    candidate_id=str(persisted["id"]),
                    generation_id=str(candidate["generation_id"]),
                    target_tool=target_tool or settings.PUBLISH_DEFAULT_ANIMATION_TOOL,
                    executor_profile_id=str(executor_profile["id"]),
                    executor_mode=str(executor_profile["executor_mode"]),
                    sequence_run_id=run.id,
                    sequence_shot_id=shot.id,
                    content_mode=content_mode,
                    rank_score=float(candidate["rank_score"]),
                )
                animation_jobs.append(job)
                await save_shot_clip(
                    sequence_shot_id=shot.id,
                    content_mode=content_mode,
                    policy_profile_id=blueprint.policy_profile_id,
                    selected_animation_job_id=job["id"],
                    retry_count=retry_count,
                    is_degraded=retry_count > 0,
                )

            shot_results.append(
                {
                    "shot": shot,
                    "prompt_packet": packet,
                    "anchor_candidates": persisted_candidates,
                    "animation_jobs": animation_jobs,
                }
            )

        refreshed_run = await update_run_status(run.id, "animating")
        return {
            "run": refreshed_run or run,
            "shots": shot_results,
            "executor_profile": executor_profile,
        }

    async def register_shot_retry(
        self,
        *,
        sequence_shot_id: str,
        content_mode: str,
        policy_profile_id: str,
        selected_animation_job_id: str | None = None,
        clip_path: str | None = None,
        clip_duration_sec: float | None = None,
        clip_score: float | None = None,
        retry_count: int = 0,
        is_degraded: bool = False,
    ) -> dict[str, Any]:
        return await save_shot_clip(
            sequence_shot_id=sequence_shot_id,
            content_mode=content_mode,
            policy_profile_id=policy_profile_id,
            selected_animation_job_id=selected_animation_job_id,
            clip_path=clip_path,
            clip_duration_sec=clip_duration_sec,
            clip_score=clip_score,
            retry_count=retry_count,
            is_degraded=is_degraded,
        )
