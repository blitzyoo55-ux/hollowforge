from __future__ import annotations

import json

import pytest

from app.db import get_db, init_db
from app.services.legacy_production_verification_backfill import (
    scan_legacy_verification_artifact_candidates,
)


def _json_list(*values: str) -> str:
    return json.dumps(list(values), separators=(",", ":"))


async def _seed_cluster(
    *,
    work_id: str,
    work_title: str,
    series_id: str,
    series_title: str,
    production_episode_id: str,
    production_episode_title: str,
    comic_episode_id: str | None,
    comic_episode_title: str | None,
    sequence_blueprint_id: str | None,
    record_origin: str = "operator",
    verification_run_id: str | None = None,
    work_created_at: str = "2026-04-18T06:00:00+00:00",
    series_created_at: str = "2026-04-18T06:03:00+00:00",
    production_episode_created_at: str = "2026-04-18T06:05:00+00:00",
) -> None:
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO works (
                id, title, format_family, default_content_mode, status, canon_notes,
                record_origin, verification_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                work_id,
                work_title,
                "mixed",
                "adult_nsfw",
                "draft",
                None,
                record_origin,
                verification_run_id,
                work_created_at,
                work_created_at,
            ),
        )
        await db.execute(
            """
            INSERT INTO series (
                id, work_id, title, delivery_mode, audience_mode, visual_identity_notes,
                record_origin, verification_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                series_id,
                work_id,
                series_title,
                "serial",
                "adult_nsfw",
                None,
                record_origin,
                verification_run_id,
                series_created_at,
                series_created_at,
            ),
        )
        await db.execute(
            """
            INSERT INTO production_episodes (
                id, work_id, series_id, title, synopsis, content_mode, target_outputs,
                continuity_summary, status, record_origin, verification_run_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                production_episode_id,
                work_id,
                series_id,
                production_episode_title,
                "Seeded synopsis",
                "adult_nsfw",
                _json_list("comic", "animation"),
                None,
                "draft",
                record_origin,
                verification_run_id,
                production_episode_created_at,
                production_episode_created_at,
            ),
        )
        if comic_episode_id and comic_episode_title:
            await db.execute(
                """
                INSERT INTO comic_episodes (
                    id, character_id, character_version_id, title, synopsis, source_story_plan_json,
                    status, continuity_summary, canon_delta, target_output, created_at, updated_at,
                    content_mode, work_id, series_id, production_episode_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comic_episode_id,
                    "char_camila_duarte",
                    "charver_camila_duarte_still_v1",
                    comic_episode_title,
                    "Seeded comic synopsis",
                    None,
                    "planned",
                    None,
                    None,
                    "oneshot_manga",
                    production_episode_created_at,
                    production_episode_created_at,
                    "adult_nsfw",
                    work_id,
                    series_id,
                    production_episode_id,
                ),
            )
        if sequence_blueprint_id:
            await db.execute(
                """
                INSERT INTO sequence_blueprints (
                    id, content_mode, policy_profile_id, character_id, location_id, beat_grammar_id,
                    target_duration_sec, shot_count, tone, executor_policy, created_at, updated_at,
                    work_id, series_id, production_episode_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sequence_blueprint_id,
                    "adult_nsfw",
                    "adult_stage1_v1",
                    "char_camila_duarte",
                    "loc_smoke",
                    "adult_stage1_v1",
                    36,
                    6,
                    "tense",
                    "adult_remote_prod",
                    production_episode_created_at,
                    production_episode_created_at,
                    work_id,
                    series_id,
                    production_episode_id,
                ),
            )
        await db.commit()


@pytest.mark.asyncio
async def test_scan_legacy_verification_artifact_candidates_classifies_clusters(temp_db) -> None:
    await init_db()

    await _seed_cluster(
        work_id="work_matched",
        work_title="Smoke Work 20260418",
        series_id="series_matched",
        series_title="Smoke Series 20260418",
        production_episode_id="prod_ep_matched",
        production_episode_title="Smoke Production Episode",
        comic_episode_id="comic_ep_matched",
        comic_episode_title="Smoke Comic Track",
        sequence_blueprint_id="blueprint_matched",
    )
    await _seed_cluster(
        work_id="work_ambiguous",
        work_title="Smoke Work 20260418 B",
        series_id="series_ambiguous",
        series_title="Smoke Series 20260418 B",
        production_episode_id="prod_ep_ambiguous",
        production_episode_title="Smoke Production Episode",
        comic_episode_id=None,
        comic_episode_title=None,
        sequence_blueprint_id="blueprint_ambiguous",
    )
    await _seed_cluster(
        work_id="work_operator",
        work_title="Operator Work",
        series_id="series_operator",
        series_title="Season One",
        production_episode_id="prod_ep_operator",
        production_episode_title="Episode 01",
        comic_episode_id="comic_ep_operator",
        comic_episode_title="Operator Comic Track",
        sequence_blueprint_id="blueprint_operator",
    )

    summary = await scan_legacy_verification_artifact_candidates()

    assert [cluster.production_episode_id for cluster in summary.matched_clusters] == [
        "prod_ep_matched",
    ]
    assert [cluster.production_episode_id for cluster in summary.ambiguous_clusters] == [
        "prod_ep_ambiguous",
    ]
    assert [cluster.production_episode_id for cluster in summary.non_match_clusters] == [
        "prod_ep_operator",
    ]
    assert summary.matched_clusters[0].work_id == "work_matched"
    assert summary.ambiguous_clusters[0].reason


@pytest.mark.asyncio
async def test_scan_legacy_verification_artifact_candidates_ignores_corrected_and_lineaged_clusters(
    temp_db,
) -> None:
    await init_db()

    await _seed_cluster(
        work_id="work_corrected",
        work_title="Smoke Work corrected",
        series_id="series_corrected",
        series_title="Smoke Series corrected",
        production_episode_id="prod_ep_corrected",
        production_episode_title="Smoke Production Episode",
        comic_episode_id="comic_ep_corrected",
        comic_episode_title="Smoke Comic Track",
        sequence_blueprint_id="blueprint_corrected",
        record_origin="verification_smoke",
    )
    await _seed_cluster(
        work_id="work_lineaged",
        work_title="Smoke Work lineaged",
        series_id="series_lineaged",
        series_title="Smoke Series lineaged",
        production_episode_id="prod_ep_lineaged",
        production_episode_title="Smoke Production Episode",
        comic_episode_id="comic_ep_lineaged",
        comic_episode_title="Smoke Comic Track",
        sequence_blueprint_id="blueprint_lineaged",
        verification_run_id="run-legacy-1",
    )

    summary = await scan_legacy_verification_artifact_candidates()

    assert summary.matched_clusters == []
    assert summary.ambiguous_clusters == []
    assert summary.non_match_clusters == []
    assert summary.ignored_production_episode_ids == [
        "prod_ep_corrected",
        "prod_ep_lineaged",
    ]
