from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import ComicEpisodeCreate
from app.services.comic_repository import create_comic_episode


def _build_client() -> TestClient:
    app = create_app(lightweight=True)
    return TestClient(app)


def _post_comic_verification_run(
    client: TestClient,
    *,
    run_mode: str,
    status: str,
    overall_success: bool,
    finished_at: str,
    started_at: str = "2026-04-17T00:00:00+00:00",
    total_duration_sec: float = 1.0,
    failure_stage: str | None = None,
    error_summary: str | None = None,
) -> dict:
    payload = {
        "run_mode": run_mode,
        "status": status,
        "overall_success": overall_success,
        "base_url": "http://127.0.0.1:8000",
        "total_duration_sec": total_duration_sec,
        "started_at": started_at,
        "finished_at": finished_at,
        "stage_status": {
            run_mode: {
                "status": "passed" if overall_success else "failed",
                "duration_sec": total_duration_sec,
                "error_summary": error_summary,
            }
        },
    }
    if failure_stage is not None:
        payload["failure_stage"] = failure_stage
    if error_summary is not None:
        payload["error_summary"] = error_summary

    response = client.post("/api/v1/production/comic-verification/runs", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_get_production_episode(temp_db) -> None:
    client = _build_client()

    work_response = client.post(
        "/api/v1/production/works",
        json={
            "id": "work_test",
            "title": "Camila Project",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
        },
    )
    assert work_response.status_code == 201
    assert work_response.json()["id"] == "work_test"

    series_response = client.post(
        "/api/v1/production/series",
        json={
            "id": "series_test",
            "work_id": "work_test",
            "title": "Season One",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
        },
    )
    assert series_response.status_code == 201
    assert series_response.json()["id"] == "series_test"

    episode_response = client.post(
        "/api/v1/production/episodes",
        json={
            "work_id": "work_test",
            "series_id": "series_test",
            "title": "Episode 01",
            "synopsis": "Camila starts a new arc.",
            "content_mode": "adult_nsfw",
            "target_outputs": ["comic", "animation"],
        },
    )
    assert episode_response.status_code == 201

    payload = episode_response.json()
    assert payload["content_mode"] == "adult_nsfw"
    assert payload["comic_track"] is None
    assert payload["animation_track"] is None

    detail_response = client.get(f"/api/v1/production/episodes/{payload['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["title"] == "Episode 01"

    list_response = client.get("/api/v1/production/episodes")
    assert list_response.status_code == 200
    assert [row["id"] for row in list_response.json()] == [payload["id"]]


def test_create_and_list_production_works_and_series_without_client_ids(temp_db) -> None:
    client = _build_client()

    work_response = client.post(
        "/api/v1/production/works",
        json={
            "title": "Camila Project",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
        },
    )
    assert work_response.status_code == 201
    work_id = work_response.json()["id"]
    assert work_id

    series_response = client.post(
        "/api/v1/production/series",
        json={
            "work_id": work_id,
            "title": "Season One",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
        },
    )
    assert series_response.status_code == 201

    works_response = client.get("/api/v1/production/works")
    assert works_response.status_code == 200
    assert [row["id"] for row in works_response.json()] == [work_id]

    series_list_response = client.get("/api/v1/production/series", params={"work_id": work_id})
    assert series_list_response.status_code == 200
    assert [row["work_id"] for row in series_list_response.json()] == [work_id]


def test_production_episode_detail_reports_track_counts(temp_db) -> None:
    client = _build_client()

    work_response = client.post(
        "/api/v1/production/works",
        json={
            "id": "work_tracks",
            "title": "Camila Project",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
        },
    )
    assert work_response.status_code == 201

    series_response = client.post(
        "/api/v1/production/series",
        json={
            "id": "series_tracks",
            "work_id": "work_tracks",
            "title": "Season One",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
        },
    )
    assert series_response.status_code == 201

    episode_response = client.post(
        "/api/v1/production/episodes",
        json={
            "work_id": "work_tracks",
            "series_id": "series_tracks",
            "title": "Episode 01",
            "synopsis": "Camila starts a new arc.",
            "content_mode": "adult_nsfw",
            "target_outputs": ["comic", "animation"],
        },
    )
    assert episode_response.status_code == 201
    payload = episode_response.json()
    assert payload["comic_track_count"] == 0
    assert payload["animation_track_count"] == 0

    episode_id = payload["id"]
    blueprint_response = client.post(
        "/api/v1/sequences/blueprints",
        json={
            "production_episode_id": episode_id,
            "work_id": "work_tracks",
            "series_id": "series_tracks",
            "content_mode": "adult_nsfw",
            "policy_profile_id": "adult_stage1_v1",
            "character_id": "char_1",
            "location_id": "location_1",
            "beat_grammar_id": "adult_stage1_v1",
            "target_duration_sec": 36,
            "shot_count": 6,
            "executor_policy": "adult_remote_prod",
        },
    )
    assert blueprint_response.status_code == 201, blueprint_response.text

    asyncio.run(
        create_comic_episode(
            ComicEpisodeCreate(
                character_id="char_kaede_ren",
                character_version_id="charver_kaede_ren_still_v1",
                title="Episode 01 Comic Track",
                synopsis="Linked comic track.",
                content_mode="adult_nsfw",
                production_episode_id=episode_id,
                work_id="work_tracks",
                series_id="series_tracks",
            ),
            episode_id="comic_track_ep_01",
        )
    )

    refreshed_response = client.get(f"/api/v1/production/episodes/{episode_id}")
    assert refreshed_response.status_code == 200
    refreshed_payload = refreshed_response.json()
    assert refreshed_payload["comic_track_count"] == 1
    assert refreshed_payload["animation_track_count"] == 1


def test_create_and_list_comic_verification_runs(temp_db) -> None:
    client = _build_client()

    created_preflight = _post_comic_verification_run(
        client,
        run_mode="preflight",
        status="completed",
        overall_success=True,
        finished_at="2026-04-17T00:00:01+00:00",
        total_duration_sec=1.2,
    )
    created_suite_1 = _post_comic_verification_run(
        client,
        run_mode="suite",
        status="completed",
        overall_success=True,
        finished_at="2026-04-17T00:00:02+00:00",
        total_duration_sec=1.3,
    )
    _post_comic_verification_run(
        client,
        run_mode="suite",
        status="completed",
        overall_success=True,
        finished_at="2026-04-17T00:00:03+00:00",
        total_duration_sec=1.4,
    )
    _post_comic_verification_run(
        client,
        run_mode="suite",
        status="completed",
        overall_success=True,
        finished_at="2026-04-17T00:00:04+00:00",
        total_duration_sec=1.5,
    )
    _post_comic_verification_run(
        client,
        run_mode="suite",
        status="failed",
        overall_success=False,
        failure_stage="suite",
        error_summary="stage 2 failed",
        finished_at="2026-04-17T00:00:05+00:00",
        total_duration_sec=1.6,
    )
    created_suite_latest = _post_comic_verification_run(
        client,
        run_mode="suite",
        status="completed",
        overall_success=True,
        finished_at="2026-04-17T00:00:06+00:00",
        total_duration_sec=1.7,
    )

    assert created_preflight["run_mode"] == "preflight"
    assert created_suite_1["stage_status"]["suite"]["status"] == "passed"
    assert created_suite_latest["status"] == "completed"

    summary_response = client.get("/api/v1/production/comic-verification/summary")
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()

    assert summary["latest_preflight"]["run_mode"] == "preflight"
    assert summary["latest_suite"]["run_mode"] == "suite"
    assert summary["recent_runs"][0]["finished_at"] == "2026-04-17T00:00:06+00:00"
    assert len(summary["recent_runs"]) == 5

    rejected_limit_response = client.get(
        "/api/v1/production/comic-verification/summary",
        params={"limit": 2},
    )
    assert rejected_limit_response.status_code == 400, rejected_limit_response.text
    assert rejected_limit_response.json()["detail"] == "comic verification summary does not support limit"


def test_production_routes_mount_in_lightweight_and_full_apps(temp_db) -> None:
    lightweight_app = create_app(lightweight=True)

    lightweight_paths = {route.path for route in lightweight_app.routes}
    main_source = Path("app/main.py").read_text(encoding="utf-8")

    assert "/api/v1/production/episodes" in lightweight_paths
    assert "/api/v1/production/comic-verification/runs" in lightweight_paths
    assert "/api/v1/production/comic-verification/summary" in lightweight_paths
    assert main_source.count("app.include_router(production.router)") == 2
