from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path


def _module_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "backfill_legacy_production_verification_artifacts.py"
    )


def _load_module():
    module_path = _module_path()
    assert module_path.exists(), f"Missing script: {module_path}"
    spec = importlib.util.spec_from_file_location(
        "backfill_legacy_production_verification_artifacts",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_list(*values: str) -> str:
    return json.dumps(list(values), separators=(",", ":"))


def _seed_cluster(
    temp_db: Path,
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
    with sqlite3.connect(temp_db) as conn:
        conn.execute(
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
        conn.execute(
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
        conn.execute(
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
            conn.execute(
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
            conn.execute(
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
        conn.commit()


def _top_level_record_origin(temp_db: Path, table: str, record_id: str) -> tuple[str | None, str | None]:
    with sqlite3.connect(temp_db) as conn:
        row = conn.execute(
            f"SELECT record_origin, verification_run_id FROM {table} WHERE id = ?",
            (record_id,),
        ).fetchone()
    assert row is not None
    return row[0], row[1]


def test_main_dry_run_prints_summary_and_preserves_records(temp_db: Path, capsys) -> None:
    module = _load_module()

    _seed_cluster(
        temp_db,
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
    _seed_cluster(
        temp_db,
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
    _seed_cluster(
        temp_db,
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

    assert module.main([]) == 0

    captured = capsys.readouterr()
    assert "mode: dry_run" in captured.out
    assert "matched_cluster_count: 1" in captured.out
    assert "ambiguous_cluster_count: 1" in captured.out
    assert "non_match_cluster_count: 1" in captured.out
    assert "would_update_work_ids: work_matched" in captured.out
    assert "would_update_series_ids: series_matched" in captured.out
    assert "would_update_production_episode_ids: prod_ep_matched" in captured.out
    assert _top_level_record_origin(temp_db, "works", "work_matched") == ("operator", None)
    assert _top_level_record_origin(temp_db, "series", "series_matched") == ("operator", None)
    assert _top_level_record_origin(temp_db, "production_episodes", "prod_ep_matched") == (
        "operator",
        None,
    )


def test_main_apply_updates_only_matched_top_level_records(temp_db: Path, capsys) -> None:
    module = _load_module()

    _seed_cluster(
        temp_db,
        work_id="work_matched",
        work_title="Smoke Work apply",
        series_id="series_matched",
        series_title="Smoke Series apply",
        production_episode_id="prod_ep_matched",
        production_episode_title="Smoke Production Episode",
        comic_episode_id="comic_ep_matched",
        comic_episode_title="Smoke Comic Track",
        sequence_blueprint_id="blueprint_matched",
    )
    _seed_cluster(
        temp_db,
        work_id="work_ambiguous",
        work_title="Smoke Work ambiguous",
        series_id="series_ambiguous",
        series_title="Smoke Series ambiguous",
        production_episode_id="prod_ep_ambiguous",
        production_episode_title="Smoke Production Episode",
        comic_episode_id=None,
        comic_episode_title=None,
        sequence_blueprint_id="blueprint_ambiguous",
    )
    _seed_cluster(
        temp_db,
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

    assert module.main(["--apply"]) == 0

    captured = capsys.readouterr()
    assert "mode: apply" in captured.out
    assert "matched_cluster_count: 1" in captured.out
    assert "updated_work_ids: work_matched" in captured.out
    assert "updated_series_ids: series_matched" in captured.out
    assert "updated_production_episode_ids: prod_ep_matched" in captured.out

    assert _top_level_record_origin(temp_db, "works", "work_matched") == (
        "verification_smoke",
        None,
    )
    assert _top_level_record_origin(temp_db, "series", "series_matched") == (
        "verification_smoke",
        None,
    )
    assert _top_level_record_origin(temp_db, "production_episodes", "prod_ep_matched") == (
        "verification_smoke",
        None,
    )
    assert _top_level_record_origin(temp_db, "works", "work_ambiguous") == ("operator", None)
    assert _top_level_record_origin(temp_db, "series", "series_ambiguous") == ("operator", None)
    assert _top_level_record_origin(temp_db, "production_episodes", "prod_ep_ambiguous") == (
        "operator",
        None,
    )
    assert _top_level_record_origin(temp_db, "works", "work_corrected") == (
        "verification_smoke",
        None,
    )
