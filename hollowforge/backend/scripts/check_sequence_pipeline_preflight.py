"""Operational preflight checks for HollowForge sequence Stage 1."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.services.rough_cut_service import (  # noqa: E402
    RoughCutAssemblyError,
    resolve_ffmpeg_bin,
)
from app.services.sequence_registry import (  # noqa: E402
    SequenceRegistryError,
    get_animation_executor_profile,
    get_prompt_provider_profile,
)

SEQUENCE_MIGRATION_FILENAME = "029_sequence_orchestration.sql"
REQUIRED_SEQUENCE_TABLES = (
    "sequence_blueprints",
    "sequence_runs",
    "sequence_shots",
    "shot_anchor_candidates",
    "shot_clips",
    "rough_cuts",
)
CANONICAL_EXECUTOR_PROFILES: tuple[tuple[str, str], ...] = (
    ("all_ages", "safe_local_preview"),
    ("all_ages", "safe_remote_prod"),
    ("adult_nsfw", "adult_local_preview"),
    ("adult_nsfw", "adult_remote_prod"),
)
READY_REMOTE_STATUSES = {"ok", "healthy", "ready"}


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Literal["PASS", "FAIL", "SKIP"]
    detail: str


def _pass(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, status="PASS", detail=detail)


def _fail(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, status="FAIL", detail=detail)


def _skip(name: str, detail: str) -> CheckResult:
    return CheckResult(name=name, status="SKIP", detail=detail)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _fetch_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=5) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return data


def _check_db_state() -> list[CheckResult]:
    migration_path = BACKEND_DIR / "migrations" / SEQUENCE_MIGRATION_FILENAME
    if not migration_path.exists():
        return [
            _fail(
                "db_migration_file",
                f"missing {migration_path}",
            ),
            _skip(
                "db_migration_applied",
                "migration file missing, skipping DB apply check",
            ),
            _skip(
                "sequence_tables",
                "migration file missing, skipping table inspection",
            ),
        ]

    checks = [
        _pass("db_migration_file", f"found {migration_path.name}"),
    ]

    try:
        asyncio.run(init_db())
    except Exception as exc:  # pragma: no cover - defensive operator path
        return checks + [
            _fail("db_migration_applied", str(exc)),
            _skip("sequence_tables", "database initialization failed"),
        ]

    try:
        with sqlite3.connect(settings.DB_PATH) as conn:
            applied = conn.execute(
                "SELECT 1 FROM schema_migrations WHERE filename = ?",
                (SEQUENCE_MIGRATION_FILENAME,),
            ).fetchone()
            table_rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        return checks + [
            _fail("db_migration_applied", f"could not inspect database: {exc}"),
            _skip("sequence_tables", "database inspection failed"),
        ]

    checks.append(
        _pass("db_migration_applied", f"{SEQUENCE_MIGRATION_FILENAME} recorded in schema_migrations")
        if applied
        else _fail(
            "db_migration_applied",
            f"{SEQUENCE_MIGRATION_FILENAME} not recorded in schema_migrations",
        )
    )

    present_tables = {str(row[0]) for row in table_rows}
    missing_tables = [name for name in REQUIRED_SEQUENCE_TABLES if name not in present_tables]
    checks.append(
        _pass("sequence_tables", ", ".join(REQUIRED_SEQUENCE_TABLES))
        if not missing_tables
        else _fail("sequence_tables", f"missing tables: {', '.join(missing_tables)}")
    )
    return checks


def _check_prompt_profiles() -> list[CheckResult]:
    checks: list[CheckResult] = []
    for content_mode, profile_id in (
        ("all_ages", settings.HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE),
        ("adult_nsfw", settings.HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE),
    ):
        name = f"prompt_profile:{content_mode}"
        try:
            profile = get_prompt_provider_profile(profile_id, content_mode=content_mode)
        except SequenceRegistryError as exc:
            checks.append(_fail(name, str(exc)))
            continue
        checks.append(
            _pass(
                name,
                f"{profile['id']} ({profile['provider_kind']}, strict_json={profile['strict_json']})",
            )
        )
    return checks


def _canonical_executor_checks() -> list[CheckResult]:
    checks: list[CheckResult] = []
    for content_mode, profile_id in CANONICAL_EXECUTOR_PROFILES:
        name = f"executor_profile:{profile_id}"
        try:
            profile = get_animation_executor_profile(profile_id, content_mode=content_mode)
        except SequenceRegistryError as exc:
            checks.append(_fail(name, str(exc)))
            continue
        checks.append(
            _pass(
                name,
                f"content_mode={profile['content_mode']}, mode={profile['executor_mode']}, lane={profile['execution_lane']}",
            )
        )
    return checks


def _selected_executor_profile_ids(args: argparse.Namespace) -> list[str]:
    profile_ids = [str(profile_id) for profile_id in args.executor_profile_id]
    configured_key = settings.ANIMATION_EXECUTOR_KEY.strip()
    if not profile_ids and configured_key and configured_key != "default":
        profile_ids.append(configured_key)
    return profile_ids


def _selected_executor_profiles(
    args: argparse.Namespace,
) -> tuple[list[CheckResult], list[dict[str, object]]]:
    checks: list[CheckResult] = []
    profiles: list[dict[str, object]] = []
    for profile_id in _selected_executor_profile_ids(args):
        try:
            profiles.append(get_animation_executor_profile(profile_id))
        except SequenceRegistryError as exc:
            checks.append(_fail(f"selected_executor_profile:{profile_id}", str(exc)))
            continue
        profile = profiles[-1]
        checks.append(
            _pass(
                f"selected_executor_profile:{profile_id}",
                f"content_mode={profile['content_mode']}, mode={profile['executor_mode']}, lane={profile['execution_lane']}",
            )
        )
    return checks, profiles


def _check_ffmpeg() -> CheckResult:
    try:
        resolved = resolve_ffmpeg_bin()
    except RoughCutAssemblyError as exc:
        return _fail("ffmpeg_bin", str(exc))
    return _pass("ffmpeg_bin", f"resolved to {resolved}")


def _check_remote_worker(
    args: argparse.Namespace,
    selected_profiles: list[dict[str, object]],
) -> CheckResult:
    selected_remote_profiles = [
        str(profile["id"])
        for profile in selected_profiles
        if profile.get("executor_mode") == "remote_worker"
    ]

    must_check = args.worker_check == "require"
    if not selected_remote_profiles and not must_check:
        return _skip(
            "remote_worker_health",
            "no remote executor profile selected; skipping worker reachability",
        )

    base_url = settings.ANIMATION_REMOTE_BASE_URL.strip()
    if not base_url:
        return _fail(
            "remote_worker_health",
            "HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL is not configured",
        )

    health_url = _join_url(base_url, "/healthz")
    try:
        payload = _fetch_json(health_url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return _fail("remote_worker_health", str(exc))

    status = payload.get("status")
    normalized_status = str(status).strip().lower()
    if normalized_status not in READY_REMOTE_STATUSES:
        return _fail(
            "remote_worker_health",
            f"{health_url} unhealthy status={status!r}",
        )
    for key in ("healthy", "ready", "accepting_jobs"):
        if key in payload and payload[key] is False:
            return _fail(
                "remote_worker_health",
                f"{health_url} unhealthy {key}=False",
            )

    backend = payload.get("executor_backend")
    profile_detail = ", ".join(selected_remote_profiles) if selected_remote_profiles else "forced check"
    return _pass(
        "remote_worker_health",
        f"{health_url} status={status} executor_backend={backend} profiles={profile_detail}",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check HollowForge sequence Stage 1 preflight requirements.",
    )
    parser.add_argument(
        "--executor-profile-id",
        action="append",
        default=[],
        help=(
            "Sequence animation executor profile to treat as selected. "
            "Repeat for multiple lanes. Remote profiles trigger worker health checks in auto mode."
        ),
    )
    parser.add_argument(
        "--worker-check",
        choices=("auto", "skip", "require"),
        default="auto",
        help="Control remote worker reachability checks. Default: auto.",
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    checks: list[CheckResult] = []
    checks.extend(_check_db_state())
    checks.extend(_check_prompt_profiles())
    checks.extend(_canonical_executor_checks())
    selected_profile_checks, selected_profiles = _selected_executor_profiles(args)
    checks.extend(selected_profile_checks)
    checks.append(_check_ffmpeg())
    if args.worker_check == "skip":
        checks.append(_skip("remote_worker_health", "skipped by --worker-check=skip"))
    else:
        checks.append(_check_remote_worker(args, selected_profiles))

    has_failures = any(check.status == "FAIL" for check in checks)

    print("HollowForge Sequence Stage 1 Preflight")
    print(f"backend: {BACKEND_DIR}")
    print(f"db_path: {settings.DB_PATH}")
    selected_profile_ids = _selected_executor_profile_ids(args)
    if args.executor_profile_id:
        print(f"selected_executor_profiles: {', '.join(args.executor_profile_id)}")
    elif selected_profile_ids:
        print(f"selected_executor_profiles: {', '.join(selected_profile_ids)} (from env)")
    else:
        print("selected_executor_profiles: none")

    for check in checks:
        print(f"[{check.status}] {check.name}: {check.detail}")

    return 1 if has_failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
