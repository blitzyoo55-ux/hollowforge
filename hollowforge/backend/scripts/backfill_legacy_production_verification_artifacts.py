"""Reclassify obvious legacy Production Hub smoke artifacts."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = Path(__file__).resolve().parents[1]
for candidate in (SCRIPT_DIR, BACKEND_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.services.legacy_production_verification_backfill import (
    BackfillApplySummary,
    BackfillScanSummary,
    apply_legacy_verification_artifact_backfill,
    scan_legacy_verification_artifact_candidates,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Update matched top-level production records in place.",
    )
    return parser


def _format_ids(values: list[str]) -> str:
    return ",".join(values) if values else "-"


def _collect_work_ids(summary: BackfillScanSummary | BackfillApplySummary) -> list[str]:
    values: list[str] = []
    for cluster in summary.matched_clusters:
        if cluster.work_id not in values:
            values.append(cluster.work_id)
    return values


def _collect_series_ids(summary: BackfillScanSummary | BackfillApplySummary) -> list[str]:
    values: list[str] = []
    for cluster in summary.matched_clusters:
        if cluster.series_id and cluster.series_id not in values:
            values.append(cluster.series_id)
    return values


def _collect_production_episode_ids(
    summary: BackfillScanSummary | BackfillApplySummary,
) -> list[str]:
    return [cluster.production_episode_id for cluster in summary.matched_clusters]


def _print_common_summary(
    *,
    mode: str,
    summary: BackfillScanSummary | BackfillApplySummary,
) -> None:
    print(f"mode: {mode}")
    print(f"matched_cluster_count: {len(summary.matched_clusters)}")
    print(
        "matched_cluster_ids: "
        f"{_format_ids([cluster.production_episode_id for cluster in summary.matched_clusters])}"
    )
    print(f"ambiguous_cluster_count: {len(summary.ambiguous_clusters)}")
    print(
        "ambiguous_cluster_ids: "
        f"{_format_ids([cluster.production_episode_id for cluster in summary.ambiguous_clusters])}"
    )
    print(f"non_match_cluster_count: {len(summary.non_match_clusters)}")
    print(
        "ignored_production_episode_ids: "
        f"{_format_ids(summary.ignored_production_episode_ids)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.apply:
            summary = asyncio.run(apply_legacy_verification_artifact_backfill())
            _print_common_summary(mode="apply", summary=summary)
            print(f"updated_work_ids: {_format_ids(summary.updated_work_ids)}")
            print(f"updated_series_ids: {_format_ids(summary.updated_series_ids)}")
            print(
                "updated_production_episode_ids: "
                f"{_format_ids(summary.updated_production_episode_ids)}"
            )
            return 0

        summary = asyncio.run(scan_legacy_verification_artifact_candidates())
        _print_common_summary(mode="dry_run", summary=summary)
        print(f"would_update_work_ids: {_format_ids(_collect_work_ids(summary))}")
        print(f"would_update_series_ids: {_format_ids(_collect_series_ids(summary))}")
        print(
            "would_update_production_episode_ids: "
            f"{_format_ids(_collect_production_episode_ids(summary))}"
        )
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
