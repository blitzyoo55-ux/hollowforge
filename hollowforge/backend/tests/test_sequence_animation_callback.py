from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.db import init_db
from app.services import sequence_repository


def _now() -> str:
    return "2026-03-26T00:00:00+00:00"

def _insert_callback_fixture(db_path: Path) -> None:
    request_json = json.dumps(
        {
            "sequence": {
                "sequence_run_id": "run_1",
                "sequence_shot_id": "shot_1",
                "content_mode": "all_ages",
                "executor_profile_id": "safe_remote_prod",
            },
            "rank_score": 0.91,
        }
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO sequence_blueprints (
                id,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "bp_1",
                "all_ages",
                "safe_stage1_v1",
                "char_1",
                "location_1",
                "stage1_single_location_v1",
                6,
                1,
                None,
                "safe_remote_prod",
                _now(),
                _now(),
            ),
        )
        conn.execute(
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
                "run_1",
                "bp_1",
                "all_ages",
                "safe_stage1_v1",
                "safe_hosted_grok",
                "remote_worker",
                "animating",
                None,
                None,
                None,
                _now(),
                _now(),
            ),
        )
        conn.execute(
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
                "shot_1",
                "run_1",
                "all_ages",
                "safe_stage1_v1",
                1,
                "establish",
                "wide_master",
                "grounded",
                "reveal_location",
                6,
                "continuity",
                _now(),
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO generations (
                id,
                prompt,
                checkpoint,
                loras,
                seed,
                steps,
                cfg,
                width,
                height,
                sampler,
                scheduler,
                status,
                image_path,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "gen_1",
                "prompt 1",
                "checkpoint.safetensors",
                "[]",
                1,
                28,
                7.0,
                832,
                1216,
                "euler",
                "normal",
                "completed",
                "images/gen_1.png",
                _now(),
            ),
        )
        conn.execute(
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
            ) VALUES (?, NULL, ?, NULL, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, NULL, ?, ?)
            """,
            (
                "job_1",
                "gen_1",
                "custom",
                "remote_worker",
                "safe_remote_prod",
                "submitted",
                request_json,
                _now(),
                _now(),
                _now(),
            ),
        )
        conn.execute(
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
                "clip_1",
                "shot_1",
                "all_ages",
                "safe_stage1_v1",
                "job_1",
                None,
                None,
                None,
                0,
                0,
                _now(),
                _now(),
            ),
        )
        conn.commit()


@pytest.mark.asyncio
async def test_mark_shot_clip_ready_for_completed_job_updates_sequence_clip(
    temp_db: Path,
) -> None:
    await init_db()
    _insert_callback_fixture(temp_db)

    await sequence_repository.mark_shot_clip_ready_for_completed_job(
        animation_job_id="job_1",
        clip_path="https://worker.example/outputs/shot_01.mp4",
    )

    with sqlite3.connect(temp_db) as conn:
        clip_row = conn.execute(
            """
            SELECT clip_path, clip_duration_sec, clip_score
            FROM shot_clips
            WHERE selected_animation_job_id = ?
            """,
            ("job_1",),
        ).fetchone()

    assert clip_row == (
        "https://worker.example/outputs/shot_01.mp4",
        6.0,
        0.91,
    )
