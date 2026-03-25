from __future__ import annotations

from app.services.rough_cut_service import build_rough_cut_timeline
from app.services.sequence_run_service import select_anchor_candidates


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

    assert [row["generation_id"] for row in selected if row["is_selected_primary"]] == ["gen_b"]
    assert [row["generation_id"] for row in selected if row["is_selected_backup"]] == [
        "gen_c",
        "gen_d",
    ]
    assert sum(1 for row in selected if row["is_selected_primary"]) == 1
    assert sum(1 for row in selected if row["is_selected_backup"]) == 2
    assert selected[0]["rank_score"] >= selected[1]["rank_score"] >= selected[2]["rank_score"]


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
