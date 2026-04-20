"""Thin repository helpers for HollowForge sequence orchestration state."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Final, cast

from app.db import get_db
from app.models import (
    RoughCutCreate,
    RoughCutResponse,
    SequenceBlueprintCreate,
    SequenceBlueprintResponse,
    SequenceBlueprintUpdate,
    SequenceRunCreate,
    SequenceRunResponse,
    SequenceRunUpdate,
    SequenceShotCreate,
    SequenceShotResponse,
)

_UNSET: Final = object()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_json(value: str | None) -> Any:
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _normalize_anchor_candidate_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["rank_score"] = _compute_rank_score(normalized)
    normalized["is_selected_primary"] = bool(normalized.get("is_selected_primary"))
    normalized["is_selected_backup"] = bool(normalized.get("is_selected_backup"))
    return normalized


def _normalize_shot_clip_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["is_degraded"] = bool(normalized.get("is_degraded"))
    return normalized


def _validate_anchor_selection_flags(
    *,
    is_selected_primary: bool,
    is_selected_backup: bool,
) -> None:
    if is_selected_primary and is_selected_backup:
        raise ValueError("anchor candidate cannot be both primary and backup")


def _float_score(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _compute_rank_score(candidate: dict[str, Any]) -> float | None:
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
        return None
    return round(sum(present) / len(present), 6)


def _parse_sequence_request_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _normalize_clip_duration(
    value: float | int | str | None,
) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    if isinstance(value, str) and value.strip():
        try:
            return round(float(value), 6)
        except ValueError:
            return None
    return None


def _blueprint_response(row: dict[str, Any]) -> SequenceBlueprintResponse:
    return SequenceBlueprintResponse.model_validate(row)


def _run_response(row: dict[str, Any]) -> SequenceRunResponse:
    return SequenceRunResponse.model_validate(row)


def _shot_response(row: dict[str, Any]) -> SequenceShotResponse:
    return SequenceShotResponse.model_validate(row)


def _rough_cut_response(row: dict[str, Any]) -> RoughCutResponse:
    payload = dict(row)
    payload["timeline_json"] = _decode_json(cast(str | None, payload.get("timeline_json")))
    return RoughCutResponse.model_validate(payload)


def _build_update_sql(values: dict[str, Any]) -> tuple[str, list[Any]]:
    set_clause = ", ".join(f"{column} = ?" for column in values)
    return set_clause, list(values.values())


async def create_blueprint(
    payload: SequenceBlueprintCreate,
    *,
    blueprint_id: str | None = None,
) -> SequenceBlueprintResponse:
    now = _now_iso()
    created_id = blueprint_id or str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO sequence_blueprints (
                id,
                work_id,
                series_id,
                production_episode_id,
                content_mode,
                policy_profile_id,
                character_id,
                location_id,
                beat_grammar_id,
                target_duration_sec,
                shot_count,
                tone,
                executor_policy,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_id,
                payload.work_id,
                payload.series_id,
                payload.production_episode_id,
                payload.content_mode,
                payload.policy_profile_id,
                payload.character_id,
                payload.location_id,
                payload.beat_grammar_id,
                payload.target_duration_sec,
                payload.shot_count,
                payload.tone,
                payload.executor_policy,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM sequence_blueprints WHERE id = ?",
            (created_id,),
        )
        row = await cursor.fetchone()
    return _blueprint_response(cast(dict[str, Any], row))


async def get_blueprint(blueprint_id: str) -> SequenceBlueprintResponse | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM sequence_blueprints WHERE id = ?",
            (blueprint_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return _blueprint_response(cast(dict[str, Any], row))


async def list_blueprints(
    *,
    content_mode: str | None = None,
    policy_profile_id: str | None = None,
    production_episode_id: str | None = None,
) -> list[SequenceBlueprintResponse]:
    clauses: list[str] = []
    params: list[Any] = []
    if content_mode is not None:
        clauses.append("content_mode = ?")
        params.append(content_mode)
    if policy_profile_id is not None:
        clauses.append("policy_profile_id = ?")
        params.append(policy_profile_id)
    if production_episode_id is not None:
        clauses.append("production_episode_id = ?")
        params.append(production_episode_id)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT * FROM sequence_blueprints
            {where_clause}
            ORDER BY created_at DESC
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [_blueprint_response(cast(dict[str, Any], row)) for row in rows]


async def update_blueprint(
    blueprint_id: str,
    payload: SequenceBlueprintUpdate,
) -> SequenceBlueprintResponse | None:
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return await get_blueprint(blueprint_id)

    values["updated_at"] = _now_iso()
    set_clause, params = _build_update_sql(values)
    async with get_db() as db:
        cursor = await db.execute(
            f"UPDATE sequence_blueprints SET {set_clause} WHERE id = ?",
            [*params, blueprint_id],
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
        refreshed = await db.execute(
            "SELECT * FROM sequence_blueprints WHERE id = ?",
            (blueprint_id,),
        )
        row = await refreshed.fetchone()
    return _blueprint_response(cast(dict[str, Any], row))


async def delete_blueprint(blueprint_id: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM sequence_blueprints WHERE id = ?",
            (blueprint_id,),
        )
        await db.commit()
    return cursor.rowcount > 0


async def create_run(
    payload: SequenceRunCreate,
    *,
    run_id: str | None = None,
) -> SequenceRunResponse:
    now = _now_iso()
    created_id = run_id or str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO sequence_runs (
                id,
                sequence_blueprint_id,
                content_mode,
                policy_profile_id,
                prompt_provider_profile_id,
                execution_mode,
                status,
                selected_rough_cut_id,
                total_score,
                error_summary,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_id,
                payload.sequence_blueprint_id,
                payload.content_mode,
                payload.policy_profile_id,
                payload.prompt_provider_profile_id,
                payload.execution_mode,
                payload.status,
                payload.selected_rough_cut_id,
                payload.total_score,
                payload.error_summary,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM sequence_runs WHERE id = ?",
            (created_id,),
        )
        row = await cursor.fetchone()
    return _run_response(cast(dict[str, Any], row))


async def get_run(run_id: str) -> SequenceRunResponse | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM sequence_runs WHERE id = ?",
            (run_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return _run_response(cast(dict[str, Any], row))


async def list_runs(
    *,
    sequence_blueprint_id: str | None = None,
    status: str | None = None,
) -> list[SequenceRunResponse]:
    clauses: list[str] = []
    params: list[Any] = []
    if sequence_blueprint_id is not None:
        clauses.append("sequence_blueprint_id = ?")
        params.append(sequence_blueprint_id)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)

    where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT * FROM sequence_runs
            {where_clause}
            ORDER BY created_at DESC
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [_run_response(cast(dict[str, Any], row)) for row in rows]


async def update_run(
    run_id: str,
    payload: SequenceRunUpdate,
) -> SequenceRunResponse | None:
    values = payload.model_dump(exclude_unset=True)
    if not values:
        return await get_run(run_id)

    values["updated_at"] = _now_iso()
    set_clause, params = _build_update_sql(values)
    async with get_db() as db:
        cursor = await db.execute(
            f"UPDATE sequence_runs SET {set_clause} WHERE id = ?",
            [*params, run_id],
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
        refreshed = await db.execute(
            "SELECT * FROM sequence_runs WHERE id = ?",
            (run_id,),
        )
        row = await refreshed.fetchone()
    return _run_response(cast(dict[str, Any], row))


async def update_run_status(
    run_id: str,
    status: str,
    *,
    selected_rough_cut_id: str | None | object = _UNSET,
    total_score: float | None | object = _UNSET,
    error_summary: str | None | object = _UNSET,
) -> SequenceRunResponse | None:
    values: dict[str, Any] = {"status": status, "updated_at": _now_iso()}
    if selected_rough_cut_id is not _UNSET:
        values["selected_rough_cut_id"] = selected_rough_cut_id
    if total_score is not _UNSET:
        values["total_score"] = total_score
    if error_summary is not _UNSET:
        values["error_summary"] = error_summary

    set_clause, params = _build_update_sql(values)
    async with get_db() as db:
        cursor = await db.execute(
            f"UPDATE sequence_runs SET {set_clause} WHERE id = ?",
            [*params, run_id],
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
        refreshed = await db.execute(
            "SELECT * FROM sequence_runs WHERE id = ?",
            (run_id,),
        )
        row = await refreshed.fetchone()
    return _run_response(cast(dict[str, Any], row))


async def insert_shots(shots: Sequence[SequenceShotCreate]) -> list[SequenceShotResponse]:
    if not shots:
        return []

    now = _now_iso()
    shot_ids: list[str] = []
    async with get_db() as db:
        for shot in shots:
            shot_id = str(uuid.uuid4())
            shot_ids.append(shot_id)
            await db.execute(
                """
                INSERT INTO sequence_shots (
                    id,
                    sequence_run_id,
                    content_mode,
                    policy_profile_id,
                    shot_no,
                    beat_type,
                    camera_intent,
                    emotion_intent,
                    action_intent,
                    target_duration_sec,
                    continuity_rules,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shot_id,
                    shot.sequence_run_id,
                    shot.content_mode,
                    shot.policy_profile_id,
                    shot.shot_no,
                    shot.beat_type,
                    shot.camera_intent,
                    shot.emotion_intent,
                    shot.action_intent,
                    shot.target_duration_sec,
                    shot.continuity_rules,
                    now,
                    now,
                ),
            )
        await db.commit()
        placeholders = ",".join("?" for _ in shot_ids)
        cursor = await db.execute(
            f"""
            SELECT * FROM sequence_shots
            WHERE id IN ({placeholders})
            ORDER BY shot_no ASC
            """,
            shot_ids,
        )
        rows = await cursor.fetchall()
    return [_shot_response(cast(dict[str, Any], row)) for row in rows]


async def get_shot(shot_id: str) -> SequenceShotResponse | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM sequence_shots WHERE id = ?",
            (shot_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return _shot_response(cast(dict[str, Any], row))


async def list_shots(sequence_run_id: str) -> list[SequenceShotResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM sequence_shots
            WHERE sequence_run_id = ?
            ORDER BY shot_no ASC
            """,
            (sequence_run_id,),
        )
        rows = await cursor.fetchall()
    return [_shot_response(cast(dict[str, Any], row)) for row in rows]


async def create_anchor_candidate(
    *,
    sequence_shot_id: str,
    content_mode: str,
    policy_profile_id: str,
    generation_id: str,
    identity_score: float | None = None,
    location_lock_score: float | None = None,
    beat_fit_score: float | None = None,
    quality_score: float | None = None,
    is_selected_primary: bool = False,
    is_selected_backup: bool = False,
    candidate_id: str | None = None,
) -> dict[str, Any]:
    _validate_anchor_selection_flags(
        is_selected_primary=is_selected_primary,
        is_selected_backup=is_selected_backup,
    )
    now = _now_iso()
    created_id = candidate_id or str(uuid.uuid4())
    async with get_db() as db:
        if is_selected_primary:
            await db.execute(
                """
                UPDATE shot_anchor_candidates
                SET is_selected_primary = 0,
                    updated_at = ?
                WHERE sequence_shot_id = ?
                """,
                (now, sequence_shot_id),
            )
        await db.execute(
            """
            INSERT INTO shot_anchor_candidates (
                id,
                sequence_shot_id,
                content_mode,
                policy_profile_id,
                generation_id,
                identity_score,
                location_lock_score,
                beat_fit_score,
                quality_score,
                is_selected_primary,
                is_selected_backup,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_id,
                sequence_shot_id,
                content_mode,
                policy_profile_id,
                generation_id,
                identity_score,
                location_lock_score,
                beat_fit_score,
                quality_score,
                int(is_selected_primary),
                int(is_selected_backup),
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM shot_anchor_candidates WHERE id = ?",
            (created_id,),
        )
        row = await cursor.fetchone()
    return _normalize_anchor_candidate_row(cast(dict[str, Any], row))


async def list_anchor_candidates(sequence_shot_id: str) -> list[dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM shot_anchor_candidates
            WHERE sequence_shot_id = ?
            ORDER BY is_selected_primary DESC, is_selected_backup DESC, quality_score DESC, updated_at DESC
            """,
            (sequence_shot_id,),
        )
        rows = await cursor.fetchall()
    normalized = [_normalize_anchor_candidate_row(cast(dict[str, Any], row)) for row in rows]
    normalized.sort(
        key=lambda row: (
            not bool(row.get("is_selected_primary")),
            not bool(row.get("is_selected_backup")),
            -(float(row["rank_score"]) if row.get("rank_score") is not None else -1.0),
            str(row.get("updated_at") or ""),
        )
    )
    return normalized


async def update_anchor_candidate_selection(
    candidate_id: str,
    *,
    is_selected_primary: bool = False,
    is_selected_backup: bool = False,
) -> dict[str, Any] | None:
    _validate_anchor_selection_flags(
        is_selected_primary=is_selected_primary,
        is_selected_backup=is_selected_backup,
    )
    async with get_db() as db:
        existing_cursor = await db.execute(
            "SELECT sequence_shot_id FROM shot_anchor_candidates WHERE id = ?",
            (candidate_id,),
        )
        existing = await existing_cursor.fetchone()
        if existing is None:
            return None

        now = _now_iso()
        if is_selected_primary:
            await db.execute(
                """
                UPDATE shot_anchor_candidates
                SET is_selected_primary = 0,
                    updated_at = ?
                WHERE sequence_shot_id = ?
                  AND id != ?
                """,
                (now, existing["sequence_shot_id"], candidate_id),
            )
        cursor = await db.execute(
            """
            UPDATE shot_anchor_candidates
            SET is_selected_primary = ?,
                is_selected_backup = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                int(is_selected_primary),
                int(is_selected_backup),
                now,
                candidate_id,
            ),
        )
        await db.commit()
        refreshed = await db.execute(
            "SELECT * FROM shot_anchor_candidates WHERE id = ?",
            (candidate_id,),
        )
        row = await refreshed.fetchone()
    return _normalize_anchor_candidate_row(cast(dict[str, Any], row))


async def save_shot_clip(
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
    clip_id: str | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    created_id = clip_id or str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO shot_clips (
                id,
                sequence_shot_id,
                content_mode,
                policy_profile_id,
                selected_animation_job_id,
                clip_path,
                clip_duration_sec,
                clip_score,
                retry_count,
                is_degraded,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_id,
                sequence_shot_id,
                content_mode,
                policy_profile_id,
                selected_animation_job_id,
                clip_path,
                clip_duration_sec,
                clip_score,
                retry_count,
                int(is_degraded),
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM shot_clips WHERE id = ?",
            (created_id,),
        )
        row = await cursor.fetchone()
    return _normalize_shot_clip_row(cast(dict[str, Any], row))


async def list_shot_clips(sequence_shot_id: str) -> list[dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM shot_clips
            WHERE sequence_shot_id = ?
            ORDER BY updated_at DESC
            """,
            (sequence_shot_id,),
        )
        rows = await cursor.fetchall()
    return [_normalize_shot_clip_row(cast(dict[str, Any], row)) for row in rows]


async def mark_shot_clip_ready_for_completed_job(
    *,
    animation_job_id: str,
    clip_path: str,
    clip_duration_sec: float | None = None,
    clip_score: float | None = None,
) -> dict[str, Any] | None:
    normalized_clip_path = clip_path.strip()
    if not normalized_clip_path:
        raise ValueError("clip_path is required to mark a shot clip ready")

    async with get_db() as db:
        job_cursor = await db.execute(
            """
            SELECT id, request_json, output_path
            FROM animation_jobs
            WHERE id = ?
            """,
            (animation_job_id,),
        )
        job_row = await job_cursor.fetchone()
        if job_row is None:
            raise ValueError(f"Unknown animation job: {animation_job_id}")

        existing_cursor = await db.execute(
            """
            SELECT *
            FROM shot_clips
            WHERE selected_animation_job_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (animation_job_id,),
        )
        existing_clip = await existing_cursor.fetchone()

        request_json = _parse_sequence_request_json(job_row.get("request_json"))
        sequence_payload = request_json.get("sequence")
        sequence_shot_id = None
        if existing_clip is not None:
            sequence_shot_id = existing_clip.get("sequence_shot_id")
        elif isinstance(sequence_payload, dict):
            sequence_shot_id = sequence_payload.get("sequence_shot_id")
        else:
            sequence_shot_id = request_json.get("sequence_shot_id")

        if not isinstance(sequence_shot_id, str) or not sequence_shot_id:
            return None

        shot_cursor = await db.execute(
            """
            SELECT content_mode, policy_profile_id, target_duration_sec
            FROM sequence_shots
            WHERE id = ?
            """,
            (sequence_shot_id,),
        )
        shot_row = await shot_cursor.fetchone()
        if shot_row is None:
            raise ValueError(f"Unknown sequence shot: {sequence_shot_id}")

        resolved_duration = _normalize_clip_duration(clip_duration_sec)
        if resolved_duration is None:
            resolved_duration = _normalize_clip_duration(request_json.get("clip_duration_sec"))
        if resolved_duration is None:
            resolved_duration = _normalize_clip_duration(request_json.get("duration_sec"))
        if resolved_duration is None:
            frames = _normalize_clip_duration(request_json.get("frames"))
            fps = _normalize_clip_duration(request_json.get("fps"))
            if frames is not None and fps not in {None, 0.0}:
                resolved_duration = round(frames / fps, 6)
        if resolved_duration is None and existing_clip is not None:
            resolved_duration = _normalize_clip_duration(existing_clip.get("clip_duration_sec"))
        if resolved_duration is None:
            resolved_duration = _normalize_clip_duration(shot_row.get("target_duration_sec"))

        resolved_score = _normalize_clip_duration(clip_score)
        if resolved_score is None:
            resolved_score = _normalize_clip_duration(request_json.get("clip_score"))
        if resolved_score is None:
            resolved_score = _normalize_clip_duration(request_json.get("rank_score"))
        if resolved_score is None and existing_clip is not None:
            resolved_score = _normalize_clip_duration(existing_clip.get("clip_score"))

        now = _now_iso()
        if existing_clip is not None:
            await db.execute(
                """
                UPDATE shot_clips
                SET clip_path = ?,
                    clip_duration_sec = ?,
                    clip_score = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    normalized_clip_path,
                    resolved_duration,
                    resolved_score,
                    now,
                    existing_clip["id"],
                ),
            )
            clip_id = existing_clip["id"]
        else:
            clip_id = str(uuid.uuid4())
            await db.execute(
                """
                INSERT INTO shot_clips (
                    id,
                    sequence_shot_id,
                    content_mode,
                    policy_profile_id,
                    selected_animation_job_id,
                    clip_path,
                    clip_duration_sec,
                    clip_score,
                    retry_count,
                    is_degraded,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clip_id,
                    sequence_shot_id,
                    shot_row["content_mode"],
                    shot_row["policy_profile_id"],
                    animation_job_id,
                    normalized_clip_path,
                    resolved_duration,
                    resolved_score,
                    0,
                    0,
                    now,
                    now,
                ),
            )

        await db.commit()
        refreshed_cursor = await db.execute(
            "SELECT * FROM shot_clips WHERE id = ?",
            (clip_id,),
        )
        refreshed_row = await refreshed_cursor.fetchone()
    return _normalize_shot_clip_row(cast(dict[str, Any], refreshed_row))


async def create_rough_cut(
    payload: RoughCutCreate,
    *,
    rough_cut_id: str | None = None,
) -> RoughCutResponse:
    now = _now_iso()
    created_id = rough_cut_id or str(uuid.uuid4())
    timeline_json = None
    if payload.timeline_json is not None:
        timeline_json = json.dumps(payload.timeline_json)

    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO rough_cuts (
                id,
                sequence_run_id,
                content_mode,
                policy_profile_id,
                output_path,
                timeline_json,
                total_duration_sec,
                continuity_score,
                story_score,
                overall_score,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                created_id,
                payload.sequence_run_id,
                payload.content_mode,
                payload.policy_profile_id,
                payload.output_path,
                timeline_json,
                payload.total_duration_sec,
                payload.continuity_score,
                payload.story_score,
                payload.overall_score,
                now,
                now,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM rough_cuts WHERE id = ?",
            (created_id,),
        )
        row = await cursor.fetchone()
    return _rough_cut_response(cast(dict[str, Any], row))


async def list_rough_cuts(sequence_run_id: str) -> list[RoughCutResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM rough_cuts
            WHERE sequence_run_id = ?
            ORDER BY overall_score DESC, updated_at DESC
            """,
            (sequence_run_id,),
        )
        rows = await cursor.fetchall()
    return [_rough_cut_response(cast(dict[str, Any], row)) for row in rows]


async def select_rough_cut_for_run(
    run_id: str,
    rough_cut_id: str,
    *,
    total_score: float | None | object = _UNSET,
) -> SequenceRunResponse | None:
    values: dict[str, Any] = {
        "selected_rough_cut_id": rough_cut_id,
        "updated_at": _now_iso(),
    }
    if total_score is not _UNSET:
        values["total_score"] = total_score

    set_clause, params = _build_update_sql(values)
    async with get_db() as db:
        cursor = await db.execute(
            f"UPDATE sequence_runs SET {set_clause} WHERE id = ?",
            [*params, run_id],
        )
        await db.commit()
        if cursor.rowcount == 0:
            return None
        refreshed = await db.execute(
            "SELECT * FROM sequence_runs WHERE id = ?",
            (run_id,),
        )
        row = await refreshed.fetchone()
    return _run_response(cast(dict[str, Any], row))
