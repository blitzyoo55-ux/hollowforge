from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import ComicEpisodeCreate
from app.services.comic_repository import create_comic_episode
from app.services.legacy_production_verification_backfill import (
    apply_legacy_verification_artifact_backfill,
)


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


def _post_production_verification_run(
    client: TestClient,
    *,
    run_mode: str,
    status: str,
    overall_success: bool,
    finished_at: str,
    started_at: str = "2026-04-19T00:00:00+00:00",
    total_duration_sec: float = 1.0,
    failure_stage: str | None = None,
    error_summary: str | None = None,
    stage_status_key: str | None = None,
) -> dict:
    payload = {
        "run_mode": run_mode,
        "status": status,
        "overall_success": overall_success,
        "base_url": "http://127.0.0.1:8014",
        "total_duration_sec": total_duration_sec,
        "started_at": started_at,
        "finished_at": finished_at,
        "stage_status": {
            stage_status_key or run_mode: {
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

    response = client.post("/api/v1/production/verification/runs", json=payload)
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


def test_production_work_and_series_lists_hide_verification_artifacts_by_default(
    temp_db,
) -> None:
    client = _build_client()

    operator_work = client.post(
        "/api/v1/production/works",
        json={
            "id": "work_operator",
            "title": "Operator Work",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
        },
    )
    assert operator_work.status_code == 201

    smoke_work = client.post(
        "/api/v1/production/works",
        json={
            "id": "work_smoke",
            "title": "Smoke Work",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
            "record_origin": "verification_smoke",
            "verification_run_id": "run-smoke-1",
        },
    )
    assert smoke_work.status_code == 201

    operator_series = client.post(
        "/api/v1/production/series",
        json={
            "id": "series_operator",
            "work_id": "work_operator",
            "title": "Operator Series",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
        },
    )
    assert operator_series.status_code == 201

    smoke_series = client.post(
        "/api/v1/production/series",
        json={
            "id": "series_smoke",
            "work_id": "work_operator",
            "title": "Smoke Series",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
            "record_origin": "verification_smoke",
            "verification_run_id": "run-smoke-1",
        },
    )
    assert smoke_series.status_code == 201

    works_response = client.get("/api/v1/production/works")
    assert works_response.status_code == 200
    assert [row["id"] for row in works_response.json()] == ["work_operator"]

    works_with_artifacts_response = client.get(
        "/api/v1/production/works",
        params={"include_verification_artifacts": True},
    )
    assert works_with_artifacts_response.status_code == 200
    assert [row["id"] for row in works_with_artifacts_response.json()] == [
        "work_smoke",
        "work_operator",
    ]

    series_response = client.get(
        "/api/v1/production/series",
        params={"work_id": "work_operator"},
    )
    assert series_response.status_code == 200
    assert [row["id"] for row in series_response.json()] == ["series_operator"]

    series_with_artifacts_response = client.get(
        "/api/v1/production/series",
        params={
            "work_id": "work_operator",
            "include_verification_artifacts": True,
        },
    )
    assert series_with_artifacts_response.status_code == 200
    assert [row["id"] for row in series_with_artifacts_response.json()] == [
        "series_smoke",
        "series_operator",
    ]


def test_production_episode_list_hides_verification_artifacts_by_default(temp_db) -> None:
    client = _build_client()

    work_response = client.post(
        "/api/v1/production/works",
        json={
            "id": "work_episode_filters",
            "title": "Episode Filter Work",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
        },
    )
    assert work_response.status_code == 201

    series_response = client.post(
        "/api/v1/production/series",
        json={
            "id": "series_episode_filters",
            "work_id": "work_episode_filters",
            "title": "Episode Filter Series",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
        },
    )
    assert series_response.status_code == 201

    operator_episode = client.post(
        "/api/v1/production/episodes",
        json={
            "work_id": "work_episode_filters",
            "series_id": "series_episode_filters",
            "title": "Operator Episode",
            "synopsis": "Operator synopsis",
            "content_mode": "adult_nsfw",
            "target_outputs": ["comic"],
        },
    )
    assert operator_episode.status_code == 201

    smoke_episode = client.post(
        "/api/v1/production/episodes",
        json={
            "work_id": "work_episode_filters",
            "series_id": "series_episode_filters",
            "title": "Smoke Episode",
            "synopsis": "Smoke synopsis",
            "content_mode": "adult_nsfw",
            "target_outputs": ["comic"],
            "record_origin": "verification_smoke",
            "verification_run_id": "run-smoke-1",
        },
    )
    assert smoke_episode.status_code == 201

    episodes_response = client.get(
        "/api/v1/production/episodes",
        params={"work_id": "work_episode_filters"},
    )
    assert episodes_response.status_code == 200
    assert [row["title"] for row in episodes_response.json()] == ["Operator Episode"]

    episodes_with_artifacts_response = client.get(
        "/api/v1/production/episodes",
        params={
            "work_id": "work_episode_filters",
            "include_verification_artifacts": True,
        },
    )
    assert episodes_with_artifacts_response.status_code == 200
    assert [row["title"] for row in episodes_with_artifacts_response.json()] == [
        "Smoke Episode",
        "Operator Episode",
    ]


def test_legacy_smoke_backfill_hides_reclassified_records_from_default_lists(
    temp_db,
) -> None:
    client = _build_client()

    work_id = "work_legacy_smoke"
    series_id = "series_legacy_smoke"

    work_response = client.post(
        "/api/v1/production/works",
        json={
            "id": work_id,
            "title": "Smoke Work 20260418",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
        },
    )
    assert work_response.status_code == 201

    series_response = client.post(
        "/api/v1/production/series",
        json={
            "id": series_id,
            "work_id": work_id,
            "title": "Smoke Series 20260418",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
        },
    )
    assert series_response.status_code == 201

    episode_response = client.post(
        "/api/v1/production/episodes",
        json={
            "id": "prod_ep_legacy_smoke",
            "work_id": work_id,
            "series_id": series_id,
            "title": "Smoke Production Episode",
            "synopsis": "Legacy smoke artifact episode.",
            "content_mode": "adult_nsfw",
            "target_outputs": ["comic", "animation"],
        },
    )
    assert episode_response.status_code == 201
    episode_id = episode_response.json()["id"]

    asyncio.run(
        create_comic_episode(
            ComicEpisodeCreate(
                character_id="char_camila_duarte",
                character_version_id="charver_camila_duarte_still_v1",
                title="Smoke Comic Track",
                synopsis="Legacy smoke comic track.",
                content_mode="adult_nsfw",
                production_episode_id=episode_id,
                work_id=work_id,
                series_id=series_id,
            ),
            episode_id="comic_ep_legacy_smoke",
        )
    )

    blueprint_response = client.post(
        "/api/v1/sequences/blueprints",
        json={
            "production_episode_id": episode_id,
            "work_id": work_id,
            "series_id": series_id,
            "content_mode": "adult_nsfw",
            "policy_profile_id": "adult_stage1_v1",
            "character_id": "char_camila_duarte",
            "location_id": "loc_smoke",
            "beat_grammar_id": "adult_stage1_v1",
            "target_duration_sec": 36,
            "shot_count": 6,
            "executor_policy": "adult_remote_prod",
        },
    )
    assert blueprint_response.status_code == 201, blueprint_response.text

    works_before_response = client.get("/api/v1/production/works")
    assert works_before_response.status_code == 200
    assert [row["id"] for row in works_before_response.json()] == [work_id]

    series_before_response = client.get(
        "/api/v1/production/series",
        params={"work_id": work_id},
    )
    assert series_before_response.status_code == 200
    assert [row["id"] for row in series_before_response.json()] == [series_id]

    episodes_before_response = client.get(
        "/api/v1/production/episodes",
        params={"work_id": work_id},
    )
    assert episodes_before_response.status_code == 200
    assert [row["id"] for row in episodes_before_response.json()] == [episode_id]

    apply_summary = asyncio.run(apply_legacy_verification_artifact_backfill())
    assert [cluster.production_episode_id for cluster in apply_summary.matched_clusters] == [
        episode_id,
    ]
    assert apply_summary.updated_work_ids == [work_id]
    assert apply_summary.updated_series_ids == [series_id]
    assert apply_summary.updated_production_episode_ids == [episode_id]

    works_after_response = client.get("/api/v1/production/works")
    assert works_after_response.status_code == 200
    assert works_after_response.json() == []

    works_with_artifacts_response = client.get(
        "/api/v1/production/works",
        params={"include_verification_artifacts": True},
    )
    assert works_with_artifacts_response.status_code == 200
    assert [row["id"] for row in works_with_artifacts_response.json()] == [work_id]

    series_after_response = client.get(
        "/api/v1/production/series",
        params={"work_id": work_id},
    )
    assert series_after_response.status_code == 200
    assert series_after_response.json() == []

    series_with_artifacts_response = client.get(
        "/api/v1/production/series",
        params={
            "work_id": work_id,
            "include_verification_artifacts": True,
        },
    )
    assert series_with_artifacts_response.status_code == 200
    assert [row["id"] for row in series_with_artifacts_response.json()] == [series_id]

    episodes_after_response = client.get(
        "/api/v1/production/episodes",
        params={"work_id": work_id},
    )
    assert episodes_after_response.status_code == 200
    assert episodes_after_response.json() == []

    episodes_with_artifacts_response = client.get(
        "/api/v1/production/episodes",
        params={
            "work_id": work_id,
            "include_verification_artifacts": True,
        },
    )
    assert episodes_with_artifacts_response.status_code == 200
    assert [row["id"] for row in episodes_with_artifacts_response.json()] == [episode_id]


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
    for shot_count in (6, 6):
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
                "shot_count": shot_count,
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
    assert refreshed_payload["animation_track_count"] == 2


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


def test_create_and_list_production_verification_runs(temp_db) -> None:
    client = _build_client()

    created_smoke = _post_production_verification_run(
        client,
        run_mode="smoke_only",
        status="completed",
        overall_success=True,
        finished_at="2026-04-19T00:00:01+00:00",
        total_duration_sec=0.2,
        stage_status_key="smoke",
    )
    _post_production_verification_run(
        client,
        run_mode="ui_only",
        status="completed",
        overall_success=True,
        finished_at="2026-04-19T00:00:02+00:00",
        total_duration_sec=2.2,
        stage_status_key="ui",
    )
    created_suite_latest = _post_production_verification_run(
        client,
        run_mode="suite",
        status="failed",
        overall_success=False,
        failure_stage="ui",
        error_summary="stage ui exited with code 1",
        finished_at="2026-04-19T00:00:03+00:00",
        total_duration_sec=2.4,
        stage_status_key="ui",
    )

    assert created_smoke["run_mode"] == "smoke_only"
    assert created_suite_latest["stage_status"]["ui"]["status"] == "failed"
    assert created_suite_latest["status"] == "failed"

    summary_response = client.get("/api/v1/production/verification/summary")
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()

    assert summary["latest_smoke_only"]["run_mode"] == "smoke_only"
    assert summary["latest_suite"]["run_mode"] == "suite"
    assert summary["recent_runs"][0]["finished_at"] == "2026-04-19T00:00:03+00:00"
    assert len(summary["recent_runs"]) == 3


def test_production_routes_mount_in_lightweight_and_full_apps(temp_db) -> None:
    lightweight_app = create_app(lightweight=True)

    lightweight_paths = {route.path for route in lightweight_app.routes}
    main_source = Path("app/main.py").read_text(encoding="utf-8")

    assert "/api/v1/production/episodes" in lightweight_paths
    assert "/api/v1/production/comic-verification/runs" in lightweight_paths
    assert "/api/v1/production/comic-verification/summary" in lightweight_paths
    assert "/api/v1/production/verification/runs" in lightweight_paths
    assert "/api/v1/production/verification/summary" in lightweight_paths
    assert main_source.count("app.include_router(production.router)") == 2
