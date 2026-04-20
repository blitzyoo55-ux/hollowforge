"""Scan legacy production records for obvious smoke verification artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

from app.db import get_db


LEGACY_SMOKE_CLUSTER_WINDOW_SEC = 600
SMOKE_WORK_PREFIX = "Smoke Work"
SMOKE_SERIES_PREFIX = "Smoke Series"
SMOKE_PRODUCTION_EPISODE_TITLE = "Smoke Production Episode"
SMOKE_COMIC_EPISODE_TITLE = "Smoke Comic Track"


@dataclass(frozen=True)
class LegacyVerificationArtifactCluster:
    work_id: str
    series_id: str | None
    production_episode_id: str
    comic_episode_ids: list[str] = field(default_factory=list)
    sequence_blueprint_ids: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass(frozen=True)
class BackfillScanSummary:
    matched_clusters: list[LegacyVerificationArtifactCluster] = field(default_factory=list)
    ambiguous_clusters: list[LegacyVerificationArtifactCluster] = field(default_factory=list)
    non_match_clusters: list[LegacyVerificationArtifactCluster] = field(default_factory=list)
    ignored_production_episode_ids: list[str] = field(default_factory=list)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _timestamps_within_window(row: dict[str, Any]) -> bool:
    timestamps = [
        _parse_iso(cast(str | None, row.get("work_created_at"))),
        _parse_iso(cast(str | None, row.get("series_created_at"))),
        _parse_iso(cast(str | None, row.get("production_episode_created_at"))),
    ]
    present = [stamp for stamp in timestamps if stamp is not None]
    if len(present) < 2:
        return False
    window = max(present) - min(present)
    return window.total_seconds() <= LEGACY_SMOKE_CLUSTER_WINDOW_SEC


def _row_is_eligible(row: dict[str, Any]) -> bool:
    top_level_pairs = [
        (
            cast(str | None, row.get("work_record_origin")),
            cast(str | None, row.get("work_verification_run_id")),
        ),
        (
            cast(str | None, row.get("production_episode_record_origin")),
            cast(str | None, row.get("production_episode_verification_run_id")),
        ),
    ]
    if row.get("series_id") is not None:
        top_level_pairs.append(
            (
                cast(str | None, row.get("series_record_origin")),
                cast(str | None, row.get("series_verification_run_id")),
            )
        )
    return all(record_origin == "operator" and verification_run_id is None for record_origin, verification_run_id in top_level_pairs)


def _cluster_from_row(
    row: dict[str, Any],
    *,
    comic_episode_ids: list[str],
    sequence_blueprint_ids: list[str],
    reason: str | None = None,
) -> LegacyVerificationArtifactCluster:
    return LegacyVerificationArtifactCluster(
        work_id=cast(str, row["work_id"]),
        series_id=cast(str | None, row.get("series_id")),
        production_episode_id=cast(str, row["production_episode_id"]),
        comic_episode_ids=comic_episode_ids,
        sequence_blueprint_ids=sequence_blueprint_ids,
        reason=reason,
    )


def _classify_cluster(
    row: dict[str, Any],
    *,
    comic_rows: list[dict[str, Any]],
    sequence_rows: list[dict[str, Any]],
) -> tuple[str, LegacyVerificationArtifactCluster]:
    smoke_work = cast(str, row["work_title"]).startswith(SMOKE_WORK_PREFIX)
    smoke_series = cast(str | None, row.get("series_title") or "").startswith(
        SMOKE_SERIES_PREFIX
    )
    smoke_episode = (
        cast(str, row["production_episode_title"]) == SMOKE_PRODUCTION_EPISODE_TITLE
    )
    smoke_comic_rows = [
        comic_row
        for comic_row in comic_rows
        if cast(str, comic_row["title"]) == SMOKE_COMIC_EPISODE_TITLE
    ]
    comic_episode_ids = [cast(str, comic_row["id"]) for comic_row in comic_rows]
    sequence_blueprint_ids = [cast(str, sequence_row["id"]) for sequence_row in sequence_rows]
    top_level_smoke_signature = smoke_work and smoke_series and smoke_episode
    time_aligned = _timestamps_within_window(row)

    if top_level_smoke_signature and smoke_comic_rows and time_aligned:
        return (
            "matched",
            _cluster_from_row(
                row,
                comic_episode_ids=comic_episode_ids,
                sequence_blueprint_ids=sequence_blueprint_ids,
            ),
        )

    if top_level_smoke_signature:
        missing_reasons: list[str] = []
        if not smoke_comic_rows:
            missing_reasons.append("missing smoke comic track")
        if not time_aligned:
            missing_reasons.append("timestamps outside legacy smoke window")
        reason = ", ".join(missing_reasons) or "legacy smoke signature incomplete"
        return (
            "ambiguous",
            _cluster_from_row(
                row,
                comic_episode_ids=comic_episode_ids,
                sequence_blueprint_ids=sequence_blueprint_ids,
                reason=reason,
            ),
        )

    return (
        "non_match",
        _cluster_from_row(
            row,
            comic_episode_ids=comic_episode_ids,
            sequence_blueprint_ids=sequence_blueprint_ids,
            reason="top-level titles do not match smoke signature",
        ),
    )


async def scan_legacy_verification_artifact_candidates() -> BackfillScanSummary:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT
                w.id AS work_id,
                w.title AS work_title,
                w.record_origin AS work_record_origin,
                w.verification_run_id AS work_verification_run_id,
                w.created_at AS work_created_at,
                s.id AS series_id,
                s.title AS series_title,
                s.record_origin AS series_record_origin,
                s.verification_run_id AS series_verification_run_id,
                s.created_at AS series_created_at,
                pe.id AS production_episode_id,
                pe.title AS production_episode_title,
                pe.record_origin AS production_episode_record_origin,
                pe.verification_run_id AS production_episode_verification_run_id,
                pe.created_at AS production_episode_created_at
            FROM production_episodes pe
            JOIN works w ON w.id = pe.work_id
            LEFT JOIN series s ON s.id = pe.series_id
            ORDER BY pe.created_at ASC, pe.id ASC
            """
        )
        rows = [cast(dict[str, Any], row) for row in await cursor.fetchall()]

        matched_clusters: list[LegacyVerificationArtifactCluster] = []
        ambiguous_clusters: list[LegacyVerificationArtifactCluster] = []
        non_match_clusters: list[LegacyVerificationArtifactCluster] = []
        ignored_production_episode_ids: list[str] = []

        for row in rows:
            production_episode_id = cast(str, row["production_episode_id"])
            if not _row_is_eligible(row):
                ignored_production_episode_ids.append(production_episode_id)
                continue

            comic_cursor = await db.execute(
                """
                SELECT id, title
                FROM comic_episodes
                WHERE production_episode_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (production_episode_id,),
            )
            comic_rows = [cast(dict[str, Any], comic_row) for comic_row in await comic_cursor.fetchall()]

            sequence_cursor = await db.execute(
                """
                SELECT id
                FROM sequence_blueprints
                WHERE production_episode_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (production_episode_id,),
            )
            sequence_rows = [
                cast(dict[str, Any], sequence_row)
                for sequence_row in await sequence_cursor.fetchall()
            ]

            classification, cluster = _classify_cluster(
                row,
                comic_rows=comic_rows,
                sequence_rows=sequence_rows,
            )
            if classification == "matched":
                matched_clusters.append(cluster)
            elif classification == "ambiguous":
                ambiguous_clusters.append(cluster)
            else:
                non_match_clusters.append(cluster)

    return BackfillScanSummary(
        matched_clusters=matched_clusters,
        ambiguous_clusters=ambiguous_clusters,
        non_match_clusters=non_match_clusters,
        ignored_production_episode_ids=ignored_production_episode_ids,
    )
