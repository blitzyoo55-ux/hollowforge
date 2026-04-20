from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.models import ComicEpisodeCreate
from app.models import AnimationJobCallbackPayload
from app.services import comic_render_service
from app.services.comic_repository import create_comic_episode


def _build_client() -> TestClient:
    return TestClient(create_app(lightweight=True))


def _insert_remote_render_job_fixture(temp_db: Path) -> tuple[str, str, str]:
    episode = asyncio.run(
        create_comic_episode(
            ComicEpisodeCreate(
                character_id="char_kaede_ren",
                character_version_id="charver_kaede_ren_still_v1",
                title="Remote Render Callback",
                synopsis="Kaede waits for a remote comic render callback.",
                target_output="oneshot_manga",
            ),
            episode_id="comic_ep_callback_render_queue_1",
        )
    )

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO comic_episode_scenes (
                id,
                episode_id,
                scene_no,
                premise,
                location_label,
                continuity_notes,
                involved_character_ids,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comic_scene_callback_render_queue_1",
                episode.id,
                1,
                "Kaede waits on the callback.",
                "Private Lounge",
                "Keep continuity intact.",
                '["char_kaede_ren"]',
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO comic_scene_panels (
                id,
                episode_scene_id,
                panel_no,
                panel_type,
                framing,
                camera_intent,
                action_intent,
                expression_intent,
                dialogue_intent,
                continuity_lock,
                page_target_hint,
                reading_order,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comic_panel_callback_render_queue_1",
                "comic_scene_callback_render_queue_1",
                1,
                "beat",
                "tight waist-up portrait",
                "slightly low camera",
                "Kaede waits for the result.",
                "controlled anticipation",
                "No dialogue yet.",
                "Stay on brand for the character version.",
                1,
                1,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO generations (
                id,
                prompt,
                negative_prompt,
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
                source_id,
                error_message,
                created_at,
                completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "gen-comic-callback-1",
                "Kaede watches the message arrive.",
                "avoid blur",
                "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                "[]",
                101,
                34,
                5.5,
                832,
                1216,
                "euler_ancestral",
                "normal",
                "submitted",
                None,
                "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
                None,
                "2026-04-04T00:00:00+00:00",
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO comic_panel_render_assets (
                id,
                scene_panel_id,
                generation_id,
                asset_role,
                storage_path,
                prompt_snapshot,
                quality_score,
                bubble_safe_zones,
                crop_metadata,
                render_notes,
                is_selected,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "asset-comic-callback-1",
                "comic_panel_callback_render_queue_1",
                "gen-comic-callback-1",
                "candidate",
                None,
                '{"prompt":"Kaede watches the message arrive."}',
                None,
                "[]",
                None,
                None,
                0,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO comic_render_jobs (
                id,
                scene_panel_id,
                render_asset_id,
                generation_id,
                request_index,
                source_id,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comic-render-callback-job-1",
                "comic_panel_callback_render_queue_1",
                "asset-comic-callback-1",
                "gen-comic-callback-1",
                0,
                "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
                "comic_panel_still",
                "remote_worker",
                "default",
                "submitted",
                (
                    '{"still_generation":{"checkpoint":"ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",'
                    '"source_id":"comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker"},'
                    '"comic":{"scene_panel_id":"comic_panel_callback_render_queue_1",'
                    '"render_asset_id":"asset-comic-callback-1",'
                    '"character_version_id":"charver_kaede_ren_still_v1"}}'
                ),
                "remote-job-1",
                "https://worker.test/jobs/remote-job-1",
                None,
                None,
                "2026-04-04T00:01:00+00:00",
                None,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:01:00+00:00",
            ),
        )
        conn.commit()

    return (
        "comic-render-callback-job-1",
        "gen-comic-callback-1",
        "asset-comic-callback-1",
    )


def test_comic_render_callback_requires_bearer_token(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, _, _ = _insert_remote_render_job_fixture(temp_db)
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-secret")
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        json={"status": "completed", "output_path": "images/comics/panel-1.png"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid comic render callback token"}


def test_comic_render_callback_completed_materializes_asset_and_generation(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, generation_id, asset_id = _insert_remote_render_job_fixture(temp_db)
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-secret")
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "completed",
            "external_job_id": "remote-job-1",
            "external_job_url": "https://worker.test/jobs/remote-job-1",
            "output_path": "images/comics/panel-1.png",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == job_id
    assert body["status"] == "completed"
    assert body["output_path"] == "images/comics/panel-1.png"

    with sqlite3.connect(temp_db) as conn:
        job_row = conn.execute(
            """
            SELECT status, output_path, external_job_url, error_message, completed_at
            FROM comic_render_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        generation_row = conn.execute(
            """
            SELECT status, image_path, error_message, completed_at
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        ).fetchone()
        asset_row = conn.execute(
            """
            SELECT storage_path
            FROM comic_panel_render_assets
            WHERE id = ?
            """,
            (asset_id,),
        ).fetchone()

    assert job_row == (
        "completed",
        "images/comics/panel-1.png",
        "https://worker.test/jobs/remote-job-1",
        None,
        job_row[4],
    )
    assert job_row[4] is not None
    assert generation_row == (
        "completed",
        "images/comics/panel-1.png",
        None,
        generation_row[3],
    )
    assert generation_row[3] is not None
    assert asset_row == ("images/comics/panel-1.png",)


def test_comic_render_callback_failed_preserves_placeholder_asset_and_records_error(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, generation_id, asset_id = _insert_remote_render_job_fixture(temp_db)
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-secret")
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "failed",
            "external_job_id": "remote-job-1",
            "external_job_url": "https://worker.test/jobs/remote-job-1",
            "error_message": "remote worker timeout",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "remote worker timeout"
    assert body["output_path"] is None

    with sqlite3.connect(temp_db) as conn:
        job_row = conn.execute(
            """
            SELECT status, output_path, error_message
            FROM comic_render_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        generation_row = conn.execute(
            """
            SELECT status, image_path, error_message
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        ).fetchone()
        asset_row = conn.execute(
            """
            SELECT storage_path
            FROM comic_panel_render_assets
            WHERE id = ?
            """,
            (asset_id,),
        ).fetchone()

    assert job_row == ("failed", None, "remote worker timeout")
    assert generation_row == ("failed", None, "remote worker timeout")
    assert asset_row == (None,)


def test_comic_render_callback_completed_ignores_late_failed_regression(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, generation_id, asset_id = _insert_remote_render_job_fixture(temp_db)
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-secret")
    client = _build_client()

    completed = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "completed",
            "external_job_id": "remote-job-1",
            "external_job_url": "https://worker.test/jobs/remote-job-1",
            "output_path": "images/comics/panel-1.png",
            "request_json": {"worker": {"attempt": 1}},
        },
    )
    assert completed.status_code == 200

    late_failed = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "failed",
            "external_job_id": "wrong-job",
            "external_job_url": "https://worker.test/jobs/wrong-job",
            "error_message": "late worker timeout",
            "request_json": {"worker": {"attempt": 99}},
        },
    )

    assert late_failed.status_code == 200
    body = late_failed.json()
    assert body["status"] == "completed"
    assert body["external_job_id"] == "remote-job-1"
    assert body["external_job_url"] == "https://worker.test/jobs/remote-job-1"
    assert body["output_path"] == "images/comics/panel-1.png"
    assert body["error_message"] is None
    assert body["request_json"] == {
        "still_generation": {
            "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
            "source_id": "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
        },
        "comic": {
            "scene_panel_id": "comic_panel_callback_render_queue_1",
            "render_asset_id": "asset-comic-callback-1",
            "character_version_id": "charver_kaede_ren_still_v1",
        },
        "worker": {"attempt": 1},
    }

    with sqlite3.connect(temp_db) as conn:
        job_row = conn.execute(
            """
            SELECT status, external_job_id, external_job_url, output_path, error_message, request_json
            FROM comic_render_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        generation_row = conn.execute(
            """
            SELECT status, image_path, error_message, comfyui_prompt_id
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        ).fetchone()
        asset_row = conn.execute(
            """
            SELECT storage_path, render_notes
            FROM comic_panel_render_assets
            WHERE id = ?
            """,
            (asset_id,),
        ).fetchone()

    assert job_row[:5] == (
        "completed",
        "remote-job-1",
        "https://worker.test/jobs/remote-job-1",
        "images/comics/panel-1.png",
        None,
    )
    assert json.loads(job_row[5]) == body["request_json"]
    assert generation_row == (
        "completed",
        "images/comics/panel-1.png",
        None,
        "remote-job-1",
    )
    assert asset_row == ("images/comics/panel-1.png", None)


def test_comic_render_callback_completed_ignores_duplicate_completed_payload(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, generation_id, asset_id = _insert_remote_render_job_fixture(temp_db)
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-secret")
    client = _build_client()

    first_completed = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "completed",
            "external_job_id": "remote-job-1",
            "external_job_url": "https://worker.test/jobs/remote-job-1",
            "output_path": "images/comics/panel-1.png",
            "request_json": {"worker": {"attempt": 1}},
        },
    )
    assert first_completed.status_code == 200

    duplicate_completed = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "completed",
            "external_job_id": "wrong-job",
            "external_job_url": "https://worker.test/jobs/wrong-job",
            "output_path": "images/comics/wrong.png",
            "request_json": {"worker": {"attempt": 99}},
        },
    )

    assert duplicate_completed.status_code == 200
    body = duplicate_completed.json()
    assert body["status"] == "completed"
    assert body["external_job_id"] == "remote-job-1"
    assert body["external_job_url"] == "https://worker.test/jobs/remote-job-1"
    assert body["output_path"] == "images/comics/panel-1.png"
    assert body["request_json"] == {
        "still_generation": {
            "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
            "source_id": "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
        },
        "comic": {
            "scene_panel_id": "comic_panel_callback_render_queue_1",
            "render_asset_id": "asset-comic-callback-1",
            "character_version_id": "charver_kaede_ren_still_v1",
        },
        "worker": {"attempt": 1},
    }

    with sqlite3.connect(temp_db) as conn:
        job_row = conn.execute(
            """
            SELECT status, external_job_id, external_job_url, output_path, request_json
            FROM comic_render_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        generation_row = conn.execute(
            """
            SELECT status, image_path, comfyui_prompt_id
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        ).fetchone()
        asset_row = conn.execute(
            """
            SELECT storage_path
            FROM comic_panel_render_assets
            WHERE id = ?
            """,
            (asset_id,),
        ).fetchone()

    assert job_row[:4] == (
        "completed",
        "remote-job-1",
        "https://worker.test/jobs/remote-job-1",
        "images/comics/panel-1.png",
    )
    assert json.loads(job_row[4]) == body["request_json"]
    assert generation_row == (
        "completed",
        "images/comics/panel-1.png",
        "remote-job-1",
    )
    assert asset_row == ("images/comics/panel-1.png",)


def test_comic_render_callback_merges_partial_request_json(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, _, _ = _insert_remote_render_job_fixture(temp_db)
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-secret")
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "processing",
            "request_json": {
                "still_generation": {"seed": 202},
                "comic": {"provider": "byteplus"},
                "worker": {"attempt": 2},
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_json"] == {
        "still_generation": {
            "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
            "source_id": "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
            "seed": 202,
        },
        "comic": {
            "scene_panel_id": "comic_panel_callback_render_queue_1",
            "render_asset_id": "asset-comic-callback-1",
            "character_version_id": "charver_kaede_ren_still_v1",
            "provider": "byteplus",
        },
        "worker": {"attempt": 2},
    }


def test_comic_render_callback_failed_ignores_late_processing_regression(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, generation_id, asset_id = _insert_remote_render_job_fixture(temp_db)
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-secret")
    client = _build_client()

    failed = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "failed",
            "external_job_id": "remote-job-1",
            "external_job_url": "https://worker.test/jobs/remote-job-1",
            "error_message": "remote worker timeout",
            "request_json": {"worker": {"attempt": 1}},
        },
    )
    assert failed.status_code == 200

    late_processing = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "processing",
            "external_job_id": "wrong-job",
            "external_job_url": "https://worker.test/jobs/wrong-job",
            "request_json": {"worker": {"attempt": 99}},
        },
    )

    assert late_processing.status_code == 200
    body = late_processing.json()
    assert body["status"] == "failed"
    assert body["external_job_id"] == "remote-job-1"
    assert body["external_job_url"] == "https://worker.test/jobs/remote-job-1"
    assert body["error_message"] == "remote worker timeout"
    assert body["request_json"] == {
        "still_generation": {
            "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
            "source_id": "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
        },
        "comic": {
            "scene_panel_id": "comic_panel_callback_render_queue_1",
            "render_asset_id": "asset-comic-callback-1",
            "character_version_id": "charver_kaede_ren_still_v1",
        },
        "worker": {"attempt": 1},
    }

    with sqlite3.connect(temp_db) as conn:
        job_row = conn.execute(
            """
            SELECT status, external_job_id, external_job_url, error_message, completed_at, request_json
            FROM comic_render_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        generation_row = conn.execute(
            """
            SELECT status, image_path, error_message, comfyui_prompt_id, completed_at
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        ).fetchone()
        asset_row = conn.execute(
            """
            SELECT storage_path, render_notes
            FROM comic_panel_render_assets
            WHERE id = ?
            """,
            (asset_id,),
        ).fetchone()

    assert job_row[:4] == (
        "failed",
        "remote-job-1",
        "https://worker.test/jobs/remote-job-1",
        "remote worker timeout",
    )
    assert job_row[4] is not None
    assert json.loads(job_row[5]) == body["request_json"]
    assert generation_row == (
        "failed",
        None,
        "remote worker timeout",
        "remote-job-1",
        generation_row[4],
    )
    assert generation_row[4] is not None
    assert asset_row == (None, "remote worker timeout")


@pytest.mark.asyncio
async def test_comic_render_callback_reloads_terminal_state_inside_transaction(
    temp_db: Path,
) -> None:
    job_id, generation_id, asset_id = await asyncio.to_thread(
        _insert_remote_render_job_fixture,
        temp_db,
    )

    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            UPDATE comic_render_jobs
            SET status = 'failed',
                external_job_id = 'remote-job-1',
                external_job_url = 'https://worker.test/jobs/remote-job-1',
                error_message = 'remote worker timeout',
                completed_at = '2026-04-04T00:02:00+00:00',
                request_json = ?
            WHERE id = ?
            """,
            (
                json.dumps(
                    {
                        "still_generation": {
                            "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                            "source_id": "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
                        },
                        "comic": {
                            "scene_panel_id": "comic_panel_callback_render_queue_1",
                            "render_asset_id": "asset-comic-callback-1",
                            "character_version_id": "charver_kaede_ren_still_v1",
                        },
                        "worker": {"attempt": 1},
                    },
                    ensure_ascii=False,
                ),
                job_id,
            ),
        )
        conn.execute(
            """
            UPDATE generations
            SET status = 'failed',
                error_message = 'remote worker timeout',
                comfyui_prompt_id = 'remote-job-1',
                completed_at = '2026-04-04T00:02:00+00:00'
            WHERE id = ?
            """,
            (generation_id,),
        )
        conn.execute(
            """
            UPDATE comic_panel_render_assets
            SET render_notes = 'remote worker timeout'
            WHERE id = ?
            """,
            (asset_id,),
        )
        conn.commit()

    stale_snapshot = {
        "id": job_id,
        "scene_panel_id": "comic_panel_callback_render_queue_1",
        "render_asset_id": asset_id,
        "generation_id": generation_id,
        "request_index": 0,
        "source_id": "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
        "target_tool": "comic_panel_still",
        "executor_mode": "remote_worker",
        "executor_key": "default",
        "status": "submitted",
        "request_json": '{"comic":{"scene_panel_id":"comic_panel_callback_render_queue_1"}}',
        "external_job_id": "stale-job",
        "external_job_url": "https://worker.test/jobs/stale-job",
        "output_path": None,
        "error_message": None,
        "submitted_at": "2026-04-04T00:01:00+00:00",
        "completed_at": None,
        "created_at": "2026-04-04T00:00:00+00:00",
        "updated_at": "2026-04-04T00:01:00+00:00",
    }

    original_load = comic_render_service._load_render_job_by_id

    async def _stale_load(job_id_arg: str):  # type: ignore[no-untyped-def]
        if job_id_arg == job_id:
            return dict(stale_snapshot)
        return await original_load(job_id_arg)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(comic_render_service, "_load_render_job_by_id", _stale_load)
    try:
        response = await comic_render_service.materialize_remote_render_job_callback(
            job_id=job_id,
            payload=AnimationJobCallbackPayload(
                status="processing",
                external_job_id="wrong-job",
                external_job_url="https://worker.test/jobs/wrong-job",
                request_json={"worker": {"attempt": 99}},
            ),
        )
    finally:
        monkeypatch.undo()

    assert response.status == "failed"
    assert response.external_job_id == "remote-job-1"
    assert response.external_job_url == "https://worker.test/jobs/remote-job-1"
    assert response.error_message == "remote worker timeout"

    with sqlite3.connect(temp_db) as conn:
        job_row = conn.execute(
            """
            SELECT status, external_job_id, external_job_url, error_message
            FROM comic_render_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    assert job_row == (
        "failed",
        "remote-job-1",
        "https://worker.test/jobs/remote-job-1",
        "remote worker timeout",
    )


def test_comic_render_callback_cancelled_ignores_late_submitted_regression(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job_id, generation_id, asset_id = _insert_remote_render_job_fixture(temp_db)
    monkeypatch.setattr(settings, "ANIMATION_CALLBACK_TOKEN", "comic-secret")
    client = _build_client()

    cancelled = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "cancelled",
            "external_job_id": "remote-job-1",
            "external_job_url": "https://worker.test/jobs/remote-job-1",
            "error_message": "remote worker cancelled",
            "request_json": {"worker": {"attempt": 1}},
        },
    )
    assert cancelled.status_code == 200

    late_submitted = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer comic-secret"},
        json={
            "status": "submitted",
            "external_job_id": "wrong-job",
            "external_job_url": "https://worker.test/jobs/wrong-job",
            "request_json": {"worker": {"attempt": 99}},
        },
    )

    assert late_submitted.status_code == 200
    body = late_submitted.json()
    assert body["status"] == "cancelled"
    assert body["external_job_id"] == "remote-job-1"
    assert body["external_job_url"] == "https://worker.test/jobs/remote-job-1"
    assert body["error_message"] == "remote worker cancelled"
    assert body["request_json"] == {
        "still_generation": {
            "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
            "source_id": "comic-panel-render:comic_panel_callback_render_queue_1:1:remote_worker",
        },
        "comic": {
            "scene_panel_id": "comic_panel_callback_render_queue_1",
            "render_asset_id": "asset-comic-callback-1",
            "character_version_id": "charver_kaede_ren_still_v1",
        },
        "worker": {"attempt": 1},
    }

    with sqlite3.connect(temp_db) as conn:
        job_row = conn.execute(
            """
            SELECT status, external_job_id, external_job_url, error_message, completed_at, request_json
            FROM comic_render_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        generation_row = conn.execute(
            """
            SELECT status, image_path, error_message, comfyui_prompt_id, completed_at
            FROM generations
            WHERE id = ?
            """,
            (generation_id,),
        ).fetchone()
        asset_row = conn.execute(
            """
            SELECT storage_path, render_notes
            FROM comic_panel_render_assets
            WHERE id = ?
            """,
            (asset_id,),
        ).fetchone()

    assert job_row[:4] == (
        "cancelled",
        "remote-job-1",
        "https://worker.test/jobs/remote-job-1",
        "remote worker cancelled",
    )
    assert job_row[4] is not None
    assert json.loads(job_row[5]) == body["request_json"]
    assert generation_row == (
        "cancelled",
        None,
        "remote worker cancelled",
        "remote-job-1",
        generation_row[4],
    )
    assert generation_row[4] is not None
    assert asset_row == (None, "remote worker cancelled")
