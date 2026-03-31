from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import pytest
from types import SimpleNamespace

from app.db import init_db
from app.services.animation_dispatch_service import build_remote_worker_payload
from app.services import sequence_run_service
from app.services import rough_cut_service
from app.services.rough_cut_service import RoughCutService
from app.services.sequence_run_service import (
    SequenceRunService,
    build_rough_cut_timeline,
    select_anchor_candidates,
)


def test_select_anchor_candidates_keeps_one_primary_and_two_backups() -> None:
    candidates = [
        {
            "generation_id": "gen_a",
            "identity_score": 0.65,
            "location_lock_score": 0.60,
            "beat_fit_score": 0.70,
            "quality_score": 0.75,
        },
        {
            "generation_id": "gen_b",
            "identity_score": 0.97,
            "location_lock_score": 0.95,
            "beat_fit_score": 0.90,
            "quality_score": 0.88,
        },
        {
            "generation_id": "gen_c",
            "identity_score": 0.92,
            "location_lock_score": 0.84,
            "beat_fit_score": 0.86,
            "quality_score": 0.89,
        },
        {
            "generation_id": "gen_d",
            "identity_score": 0.89,
            "location_lock_score": 0.83,
            "beat_fit_score": 0.80,
            "quality_score": 0.86,
        },
    ]

    selected = select_anchor_candidates(candidates)

    assert selected["primary"]["generation_id"] == "gen_b"
    assert [row["generation_id"] for row in selected["backups"]] == ["gen_c", "gen_d"]
    assert selected["ranked"][0]["rank_score"] >= selected["ranked"][1]["rank_score"]
    assert selected["ranked"][1]["rank_score"] >= selected["ranked"][2]["rank_score"]


def test_build_rough_cut_timeline_preserves_shot_order() -> None:
    clips = [
        {
            "sequence_shot_id": "shot_3",
            "shot_no": 3,
            "clip_path": "clips/shot_03.mp4",
            "clip_duration_sec": 2.2,
        },
        {
            "sequence_shot_id": "shot_1",
            "shot_no": 1,
            "clip_path": "clips/shot_01.mp4",
            "clip_duration_sec": 1.5,
        },
        {
            "sequence_shot_id": "shot_2",
            "shot_no": 2,
            "clip_path": "clips/shot_02.mp4",
            "clip_duration_sec": 1.8,
        },
    ]

    timeline = build_rough_cut_timeline(clips)

    assert [entry["shot_no"] for entry in timeline] == [1, 2, 3]
    assert [entry["clip_path"] for entry in timeline] == [
        "clips/shot_01.mp4",
        "clips/shot_02.mp4",
        "clips/shot_03.mp4",
    ]
    assert timeline[0]["start_sec"] == 0.0
    assert timeline[1]["start_sec"] == 1.5
    assert timeline[2]["start_sec"] == 3.3


def test_build_remote_worker_payload_preserves_sequence_metadata_for_dict_request_json() -> None:
    payload = build_remote_worker_payload(
        {
            "id": "job_1",
            "generation_id": "gen_1",
            "target_tool": "dreamactor",
            "executor_mode": "remote_worker",
            "executor_key": "safe_remote_prod",
            "request_json": {
                "sequence_run_id": "run_1",
                "sequence_shot_id": "shot_1",
                "content_mode": "all_ages",
                "executor_profile_id": "safe_remote_prod",
            },
        },
        {
            "image_path": "images/source.png",
            "checkpoint": "checkpoint.safetensors",
            "prompt": "prompt",
            "created_at": "2026-03-26T00:00:00+00:00",
        },
    )

    assert payload["request_json"] is not None
    assert payload["request_json"]["sequence"] == {
        "sequence_run_id": "run_1",
        "sequence_shot_id": "shot_1",
        "content_mode": "all_ages",
        "executor_profile_id": "safe_remote_prod",
    }


def test_resolve_ffmpeg_bin_rejects_missing_explicit_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    missing_bin = "/tmp/hollowforge-missing-ffmpeg-bin"
    monkeypatch.setattr(
        rough_cut_service.settings,
        "HOLLOWFORGE_SEQUENCE_FFMPEG_BIN",
        missing_bin,
    )

    with pytest.raises(
        rough_cut_service.RoughCutAssemblyError,
        match="ffmpeg binary not found",
    ):
        rough_cut_service.resolve_ffmpeg_bin()


def test_resolve_ffmpeg_bin_rejects_non_executable_explicit_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ffmpeg_stub = tmp_path / "ffmpeg"
    ffmpeg_stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ffmpeg_stub.chmod(0o644)
    monkeypatch.setattr(
        rough_cut_service.settings,
        "HOLLOWFORGE_SEQUENCE_FFMPEG_BIN",
        str(ffmpeg_stub),
    )

    with pytest.raises(
        rough_cut_service.RoughCutAssemblyError,
        match="ffmpeg binary not executable",
    ):
        rough_cut_service.resolve_ffmpeg_bin()


def test_sequence_runtime_adult_default_remains_local_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sequence_run_service.settings,
        "HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE",
        "adult_local_llm",
    )
    monkeypatch.setattr(
        sequence_run_service.settings,
        "HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE",
        "adult_openrouter_grok",
    )

    assert (
        sequence_run_service._default_prompt_provider_profile_id("adult_nsfw")
        == "adult_local_llm"
    )


@pytest.mark.asyncio
async def test_run_ffmpeg_wraps_permission_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ffmpeg_stub = tmp_path / "ffmpeg"
    ffmpeg_stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    ffmpeg_stub.chmod(0o755)
    monkeypatch.setattr(
        rough_cut_service.settings,
        "HOLLOWFORGE_SEQUENCE_FFMPEG_BIN",
        str(ffmpeg_stub),
    )

    async def _raise_permission_error(func):  # type: ignore[no-untyped-def]
        raise PermissionError("permission denied")

    monkeypatch.setattr(rough_cut_service.asyncio, "to_thread", _raise_permission_error)

    with pytest.raises(
        rough_cut_service.RoughCutAssemblyError,
        match="ffmpeg binary not executable",
    ):
        await rough_cut_service._run_ffmpeg(
            tmp_path / "manifest.txt",
            tmp_path / "output.mp4",
        )


class _FailIfCalledGenerationService:
    async def queue_generation_batch(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("queue_generation_batch should not be reached")


class _StubGenerationService:
    def __init__(self, generation_ids: list[str]) -> None:
        self._generation_ids = generation_ids

    async def queue_generation_batch(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return 100, [SimpleNamespace(id=generation_id) for generation_id in self._generation_ids]


def _now() -> str:
    return "2026-03-26T00:00:00+00:00"


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
                None,
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


@pytest.mark.asyncio
async def test_create_run_from_blueprint_rejects_candidate_count_below_batch_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_get_blueprint(blueprint_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            id=blueprint_id,
            content_mode="all_ages",
            policy_profile_id="safe_stage1_v1",
            executor_policy="safe_remote_prod",
        )

    monkeypatch.setattr(
        sequence_run_service,
        "get_blueprint",
        _fake_get_blueprint,
    )
    service = SequenceRunService(_FailIfCalledGenerationService())

    with pytest.raises(ValueError, match="candidate_count"):
        await service.create_run_from_blueprint(
            blueprint_id="bp_1",
            candidate_count=1,
        )


@pytest.mark.asyncio
async def test_create_run_from_blueprint_persists_sequence_jobs_without_animation_candidate_fk(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await init_db()
    _insert_blueprint(temp_db)
    generation_ids = [f"gen_{index}" for index in range(1, 25)]
    _insert_generation_rows(temp_db, generation_ids)

    monkeypatch.setattr(
        sequence_run_service,
        "load_prompt_benchmark_snapshot",
        _fake_load_prompt_benchmark_snapshot,
    )

    service = SequenceRunService(_StubGenerationService(generation_ids))
    result = await service.create_run_from_blueprint(blueprint_id="bp_1", candidate_count=4)

    assert result["run"].status == "animating"

    with sqlite3.connect(temp_db) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        jobs = conn.execute(
            """
            SELECT candidate_id, request_json
            FROM animation_jobs
            ORDER BY created_at ASC
            """
        ).fetchall()

    assert len(jobs) == 18
    assert all(row["candidate_id"] is None for row in jobs)
    first_request_json = json.loads(jobs[0]["request_json"])
    assert first_request_json["sequence"]["shot_anchor_candidate_id"] is not None
    assert first_request_json["sequence"]["sequence_run_id"] == result["run"].id


@pytest.mark.asyncio
async def test_rough_cut_service_assemble_persists_manifest_and_output(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await init_db()
    _insert_blueprint(temp_db)

    with sqlite3.connect(temp_db) as conn:
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
                    json.dumps(payload.timeline_json),
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

    async def _fake_select_rough_cut_for_run(run_id: str, rough_cut_id: str):  # type: ignore[no-untyped-def]
        with sqlite3.connect(temp_db) as conn:
            conn.execute(
                "UPDATE sequence_runs SET selected_rough_cut_id = ? WHERE id = ?",
                (rough_cut_id, run_id),
            )
            conn.commit()
        return None

    monkeypatch.setattr(rough_cut_service, "create_rough_cut", _fake_create_rough_cut)
    monkeypatch.setattr(rough_cut_service, "select_rough_cut_for_run", _fake_select_rough_cut_for_run)
    monkeypatch.setattr(rough_cut_service, "_run_ffmpeg", _fake_run_ffmpeg)

    service = RoughCutService()
    result = await service.assemble(sequence_run_id="run_1")

    manifest_path = Path(result["manifest_path"])
    assert manifest_path.exists()
    assert "shot_01.mp4" in manifest_path.read_text(encoding="utf-8")
    assert "shot_02.mp4" in manifest_path.read_text(encoding="utf-8")
    assert result["rough_cut"].output_path == "sequence_runs/run_1/rough_cut.mp4"
    assert result["timeline"][0]["shot_no"] == 1
    assert result["timeline"][1]["shot_no"] == 2

    with sqlite3.connect(temp_db) as conn:
        selected_rough_cut_id = conn.execute(
            "SELECT selected_rough_cut_id FROM sequence_runs WHERE id = ?",
            ("run_1",),
        ).fetchone()[0]
        persisted_output_path = conn.execute(
            "SELECT output_path FROM rough_cuts WHERE id = ?",
            (result["rough_cut"].id,),
        ).fetchone()[0]

    assert selected_rough_cut_id == result["rough_cut"].id
    assert persisted_output_path == "sequence_runs/run_1/rough_cut.mp4"


@pytest.mark.asyncio
async def test_rough_cut_service_assemble_downloads_remote_clip_urls_before_concat(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await init_db()
    _insert_blueprint(temp_db)

    with sqlite3.connect(temp_db) as conn:
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
                    f"https://worker.example/outputs/shot_0{shot_no}.mp4",
                    1.5 if shot_no == 1 else 2.0,
                    0.9,
                    0,
                    0,
                    _now(),
                    _now(),
                ),
            )
        conn.commit()

    downloaded_paths: list[Path] = []

    async def _fake_download_remote_clip_to_local(source_url: str, destination_path: Path) -> Path:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(source_url, encoding="utf-8")
        downloaded_paths.append(destination_path)
        return destination_path

    async def _fake_run_ffmpeg(manifest_path: Path, output_path: Path) -> None:
        output_path.write_bytes(b"fake-mp4")

    async def _fake_create_rough_cut(payload):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            id="rough_cut_1",
            output_path=payload.output_path,
            timeline_json=payload.timeline_json,
            total_duration_sec=payload.total_duration_sec,
        )

    async def _fake_select_rough_cut_for_run(run_id: str, rough_cut_id: str):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(
        rough_cut_service,
        "_download_remote_clip_to_local",
        _fake_download_remote_clip_to_local,
        raising=False,
    )
    monkeypatch.setattr(rough_cut_service, "_run_ffmpeg", _fake_run_ffmpeg)
    monkeypatch.setattr(rough_cut_service, "create_rough_cut", _fake_create_rough_cut)
    monkeypatch.setattr(
        rough_cut_service,
        "select_rough_cut_for_run",
        _fake_select_rough_cut_for_run,
    )

    service = RoughCutService()
    result = await service.assemble(sequence_run_id="run_1")

    manifest_text = Path(result["manifest_path"]).read_text(encoding="utf-8")
    assert len(downloaded_paths) == 2
    assert all(path.exists() for path in downloaded_paths)
    assert "worker.example" not in manifest_text
    assert "staged_clips" in manifest_text


@pytest.mark.asyncio
async def test_rough_cut_service_assemble_refreshes_staged_remote_clip_when_url_changes(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await init_db()
    _insert_blueprint(temp_db)

    with sqlite3.connect(temp_db) as conn:
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
                "run_refresh",
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
                "shot_refresh",
                "run_refresh",
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
                "clip_refresh",
                "shot_refresh",
                "all_ages",
                "safe_stage1_v1",
                None,
                "https://worker.example/outputs/shot_refresh_v1.mp4",
                1.5,
                0.9,
                0,
                0,
                _now(),
                _now(),
            ),
        )
        conn.commit()

    download_calls: list[tuple[str, Path]] = []

    async def _fake_download_remote_clip_to_local(source_url: str, destination_path: Path) -> Path:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(source_url, encoding="utf-8")
        download_calls.append((source_url, destination_path))
        return destination_path

    async def _fake_run_ffmpeg(manifest_path: Path, output_path: Path) -> None:
        output_path.write_bytes(b"fake-mp4")

    async def _fake_create_rough_cut(payload):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            id="rough_cut_refresh",
            output_path=payload.output_path,
            timeline_json=payload.timeline_json,
            total_duration_sec=payload.total_duration_sec,
        )

    async def _fake_select_rough_cut_for_run(run_id: str, rough_cut_id: str):  # type: ignore[no-untyped-def]
        return None

    monkeypatch.setattr(
        rough_cut_service,
        "_download_remote_clip_to_local",
        _fake_download_remote_clip_to_local,
        raising=False,
    )
    monkeypatch.setattr(rough_cut_service, "_run_ffmpeg", _fake_run_ffmpeg)
    monkeypatch.setattr(rough_cut_service, "create_rough_cut", _fake_create_rough_cut)
    monkeypatch.setattr(
        rough_cut_service,
        "select_rough_cut_for_run",
        _fake_select_rough_cut_for_run,
    )

    service = RoughCutService()
    first_result = await service.assemble(sequence_run_id="run_refresh")
    first_manifest = Path(first_result["manifest_path"]).read_text(encoding="utf-8")
    first_staged_path = Path(first_manifest.split("'")[1])

    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            "UPDATE shot_clips SET clip_path = ?, updated_at = ? WHERE id = ?",
            (
                "https://worker.example/outputs/shot_refresh_v2.mp4",
                "2026-03-26T00:00:01+00:00",
                "clip_refresh",
            ),
        )
        conn.commit()

    second_result = await service.assemble(sequence_run_id="run_refresh")
    second_manifest = Path(second_result["manifest_path"]).read_text(encoding="utf-8")
    second_staged_path = Path(second_manifest.split("'")[1])

    assert [call[0] for call in download_calls] == [
        "https://worker.example/outputs/shot_refresh_v1.mp4",
        "https://worker.example/outputs/shot_refresh_v2.mp4",
    ]
    assert second_staged_path.read_text(encoding="utf-8") == (
        "https://worker.example/outputs/shot_refresh_v2.mp4"
    )
    assert first_staged_path != second_staged_path


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
