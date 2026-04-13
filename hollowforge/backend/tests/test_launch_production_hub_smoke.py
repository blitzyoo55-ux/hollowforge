from __future__ import annotations

from scripts import launch_production_hub_smoke


def test_main_prints_linked_track_success_markers(capsys, monkeypatch) -> None:
    async def _fake_run_smoke():
        return {
            "work_id": "work_demo",
            "series_id": "series_demo",
            "production_episode_id": "prod_ep_demo",
            "comic_episode_id": "comic_ep_demo",
            "comic_content_mode": "all_ages",
            "sequence_blueprint_id": "bp_demo",
            "sequence_content_mode": "all_ages",
        }

    monkeypatch.setattr(launch_production_hub_smoke, "run_smoke", _fake_run_smoke)

    assert launch_production_hub_smoke.main() == 0

    captured = capsys.readouterr().out
    assert "PRODUCTION_HUB_OK" in captured
    assert "COMIC_TRACK_OK" in captured
    assert "ANIMATION_TRACK_OK" in captured

