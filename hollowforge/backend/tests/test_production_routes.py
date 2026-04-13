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


def test_production_routes_mount_in_lightweight_and_full_apps(temp_db) -> None:
    lightweight_app = create_app(lightweight=True)

    lightweight_paths = {route.path for route in lightweight_app.routes}
    main_source = Path("app/main.py").read_text(encoding="utf-8")

    assert "/api/v1/production/episodes" in lightweight_paths
    assert main_source.count("app.include_router(production.router)") == 2
