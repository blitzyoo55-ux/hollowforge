from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.db import init_db

os.environ.setdefault("HOLLOWFORGE_LIGHTWEIGHT_APP", "1")

from app.main import create_app
from app.models import RoughCutResponse
from app.routes import sequences as sequence_routes
from app.services import rough_cut_service, sequence_run_service


def _build_client(*, generation_service=None) -> TestClient:  # type: ignore[no-untyped-def]
    app = create_app(lightweight=True)
    if generation_service is not None:
        app.state.generation_service = generation_service
    return TestClient(app)


def _now() -> str:
    return "2026-03-26T00:00:00+00:00"


def _init_test_db() -> None:
    asyncio.run(init_db())


def _insert_blueprint(db_path: Path, blueprint_id: str = "bp_1") -> None:
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
                blueprint_id,
                "all_ages",
                "safe_stage1_v1",
                "char_1",
                "location_1",
                "stage1_single_location_v1",
                36,
                6,
                "tense",
                "safe_remote_prod",
                _now(),
                _now(),
            ),
        )
        conn.commit()


def _insert_generation_rows(db_path: Path, generation_ids: list[str]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for index, generation_id in enumerate(generation_ids, start=1):
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
                    generation_id,
                    f"prompt {index}",
                    "checkpoint.safetensors",
                    "[]",
                    index,
                    28,
                    7.0,
                    832,
                    1216,
                    "euler",
                    "normal",
                    "completed",
                    f"images/{generation_id}.png",
                    _now(),
                ),
            )
        conn.commit()


def _insert_run_with_shots_and_clips(db_path: Path) -> None:
    _insert_blueprint(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
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
        for shot_no in (1, 2):
            shot_id = f"shot_{shot_no}"
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
                    shot_id,
                    "run_1",
                    "all_ages",
                    "safe_stage1_v1",
                    shot_no,
                    "establish" if shot_no == 1 else "attention",
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
                    f"clip_{shot_no}",
                    shot_id,
                    "all_ages",
                    "safe_stage1_v1",
                    None,
                    f"clips/shot_0{shot_no}.mp4",
                    1.5 if shot_no == 1 else 2.0,
                    0.9,
                    0,
                    0,
                    _now(),
                    _now(),
                ),
            )
        conn.commit()


class _StubGenerationService:
    def __init__(self, generation_ids: list[str]) -> None:
        self._generation_ids = generation_ids
        self._cursor = 0

    async def queue_generation_batch(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        count = int(kwargs["count"])
        batch_ids = self._generation_ids[self._cursor : self._cursor + count]
        self._cursor += count
        return 100, [SimpleNamespace(id=generation_id) for generation_id in batch_ids]


async def _fake_load_prompt_benchmark_snapshot(workflow_lane: str) -> SimpleNamespace:
    return SimpleNamespace(
        model_dump=lambda: {
            "negative_prompt": "negative",
            "top_checkpoints": ["checkpoint.safetensors"],
            "workflow_lane": "sdxl_illustrious",
            "sampler": "euler",
            "scheduler": "normal",
            "clip_skip": 2,
            "steps_values": [28],
            "cfg_values": [7.0],
            "width": 832,
            "height": 1216,
        }
    )


def test_create_sequence_blueprint_endpoint_is_exposed(temp_db: Path) -> None:
    _init_test_db()
    client = _build_client()

    response = client.post(
        "/api/v1/sequences/blueprints",
        json={
            "content_mode": "all_ages",
            "policy_profile_id": "safe_stage1_v1",
            "character_id": "char_1",
            "location_id": "location_1",
            "beat_grammar_id": "stage1_single_location_v1",
            "target_duration_sec": 36,
            "shot_count": 6,
            "tone": "tense",
            "executor_policy": "safe_remote_prod",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["blueprint"]["character_id"] == "char_1"
    assert len(payload["planned_shots"]) == 6
    assert payload["planned_shots"][0]["beat_type"] == "establish"


def test_list_sequence_blueprints_returns_planned_shots(temp_db: Path) -> None:
    _init_test_db()
    _insert_blueprint(temp_db)
    client = _build_client()

    response = client.get("/api/v1/sequences/blueprints")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["blueprint"]["id"] == "bp_1"
    assert len(payload[0]["planned_shots"]) == 6


def test_create_sequence_run_returns_seeded_shot_detail(
    temp_db: Path,
    monkeypatch,
) -> None:
    _init_test_db()
    _insert_blueprint(temp_db)
    generation_ids = [f"gen_{index}" for index in range(1, 25)]
    _insert_generation_rows(temp_db, generation_ids)

    monkeypatch.setattr(
        sequence_run_service,
        "load_prompt_benchmark_snapshot",
        _fake_load_prompt_benchmark_snapshot,
    )
    client = _build_client(generation_service=_StubGenerationService(generation_ids))

    response = client.post(
        "/api/v1/sequences/runs",
        json={
            "sequence_blueprint_id": "bp_1",
            "candidate_count": 4,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["run"]["status"] == "animating"
    assert payload["blueprint"]["id"] == "bp_1"
    assert len(payload["shots"]) == 6
    assert len(payload["shots"][0]["anchor_candidates"]) == 4
    assert payload["rough_cut_candidates"] == []


def test_list_sequence_runs_returns_summary_counts(
    temp_db: Path,
    monkeypatch,
) -> None:
    _init_test_db()
    _insert_blueprint(temp_db)
    generation_ids = [f"gen_{index}" for index in range(1, 25)]
    _insert_generation_rows(temp_db, generation_ids)

    monkeypatch.setattr(
        sequence_run_service,
        "load_prompt_benchmark_snapshot",
        _fake_load_prompt_benchmark_snapshot,
    )
    client = _build_client(generation_service=_StubGenerationService(generation_ids))
    create_response = client.post(
        "/api/v1/sequences/runs",
        json={
            "sequence_blueprint_id": "bp_1",
            "candidate_count": 4,
        },
    )
    run_id = create_response.json()["run"]["id"]

    response = client.get("/api/v1/sequences/runs", params={"status": "animating"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["run"]["id"] == run_id
    assert payload[0]["shot_count"] == 6
    assert payload[0]["rough_cut_candidate_count"] == 0


def test_get_sequence_run_returns_detail_with_related_records(temp_db: Path) -> None:
    _init_test_db()
    _insert_run_with_shots_and_clips(temp_db)
    client = _build_client()

    response = client.get("/api/v1/sequences/runs/run_1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == "run_1"
    assert payload["blueprint"]["id"] == "bp_1"
    assert [shot["shot"]["shot_no"] for shot in payload["shots"]] == [1, 2]
    assert payload["shots"][0]["clips"][0]["clip_path"] == "clips/shot_01.mp4"


def test_start_sequence_run_assembles_rough_cut_candidate(
    temp_db: Path,
    monkeypatch,
) -> None:
    _init_test_db()
    _insert_run_with_shots_and_clips(temp_db)

    async def _fake_run_ffmpeg(manifest_path: Path, output_path: Path) -> None:
        output_path.write_bytes(b"fake-mp4")

    async def _fake_create_rough_cut(payload):  # type: ignore[no-untyped-def]
        rough_cut_id = "rough_cut_1"
        with sqlite3.connect(temp_db) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
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
                    rough_cut_id,
                    payload.sequence_run_id,
                    payload.content_mode,
                    payload.policy_profile_id,
                    payload.output_path,
                    "[]",
                    payload.total_duration_sec,
                    payload.continuity_score,
                    payload.story_score,
                    payload.overall_score,
                    _now(),
                    _now(),
                ),
            )
            conn.commit()
        return SimpleNamespace(
            id=rough_cut_id,
            output_path=payload.output_path,
            timeline_json=payload.timeline_json,
            total_duration_sec=payload.total_duration_sec,
        )

    async def _fake_list_rough_cuts(run_id: str) -> list[RoughCutResponse]:
        return [
            RoughCutResponse(
                id="rough_cut_1",
                sequence_run_id=run_id,
                content_mode="all_ages",
                policy_profile_id="safe_stage1_v1",
                output_path="sequence_runs/run_1/rough_cut.mp4",
                timeline_json=[],
                total_duration_sec=3.5,
                continuity_score=None,
                story_score=None,
                overall_score=None,
                created_at=_now(),
                updated_at=_now(),
            )
        ]

    monkeypatch.setattr(rough_cut_service, "create_rough_cut", _fake_create_rough_cut)
    monkeypatch.setattr(rough_cut_service, "_run_ffmpeg", _fake_run_ffmpeg)
    monkeypatch.setattr(sequence_routes, "list_rough_cuts", _fake_list_rough_cuts)
    client = _build_client()

    response = client.post("/api/v1/sequences/runs/run_1/start")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["selected_rough_cut_id"] is not None
    assert len(payload["rough_cut_candidates"]) == 1
    assert payload["rough_cut_candidates"][0]["is_selected"] is True
    assert payload["rough_cut_candidates"][0]["rough_cut"]["output_path"] == (
        "sequence_runs/run_1/rough_cut.mp4"
    )
