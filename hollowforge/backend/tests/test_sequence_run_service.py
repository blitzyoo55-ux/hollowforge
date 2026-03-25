from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.services.animation_dispatch_service import build_remote_worker_payload
from app.services import sequence_run_service
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


class _FailIfCalledGenerationService:
    async def queue_generation_batch(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("queue_generation_batch should not be reached")


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
