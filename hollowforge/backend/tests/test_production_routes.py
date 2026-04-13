from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def _build_client() -> TestClient:
    app = create_app(lightweight=True)
    return TestClient(app)


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

    refreshed_response = client.get(f"/api/v1/production/episodes/{episode_id}")
    assert refreshed_response.status_code == 200
    refreshed_payload = refreshed_response.json()
    assert refreshed_payload["animation_track_count"] == 2


def test_production_routes_mount_in_lightweight_and_full_apps(temp_db) -> None:
    lightweight_app = create_app(lightweight=True)

    lightweight_paths = {route.path for route in lightweight_app.routes}
    main_source = Path("app/main.py").read_text(encoding="utf-8")

    assert "/api/v1/production/episodes" in lightweight_paths
    assert main_source.count("app.include_router(production.router)") == 2
