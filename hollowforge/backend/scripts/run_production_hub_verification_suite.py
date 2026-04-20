"""Run the production-hub smoke and focused UI tests from one operator CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
FRONTEND_DIR = REPO_ROOT / "frontend"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
STAGE_ORDER = ("smoke", "ui")
FRONTEND_TEST_TARGETS = (
    "src/pages/ProductionHub.test.tsx",
    "src/pages/ComicStudio.test.tsx",
    "src/pages/SequenceStudio.test.tsx",
)


def _print_marker(key: str, value: Any) -> None:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif value is None:
        rendered = ""
    else:
        rendered = str(value)
    print(f"{key}: {rendered}")


def _format_duration(value: float) -> str:
    return f"{max(0.0, value):.3f}"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Expected JSON object from {url}")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--smoke-only", action="store_true")
    parser.add_argument("--ui-only", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    return parser


def _select_stages(args: argparse.Namespace) -> list[str]:
    selected = [
        stage
        for stage, enabled in (
            ("smoke", args.smoke_only),
            ("ui", args.ui_only),
        )
        if enabled
    ]
    if len(selected) > 1:
        raise ValueError("choose only one stage selection flag")
    return selected or list(STAGE_ORDER)


def _resolve_stage_command(
    *,
    stage: str,
    base_url: str,
    verification_run_id: str | None = None,
) -> list[str]:
    if stage == "smoke":
        command = [
            sys.executable,
            str(SCRIPT_DIR / "launch_production_hub_smoke.py"),
            "--base-url",
            base_url,
        ]
        if verification_run_id:
            command.extend(["--verification-run-id", verification_run_id])
        return command
    if stage == "ui":
        return [
            "npm",
            "run",
            "test",
            "--",
            *FRONTEND_TEST_TARGETS,
        ]
    raise ValueError(f"Unknown production hub verification stage: {stage}")


def _resolve_stage_cwd(stage: str) -> Path:
    if stage == "smoke":
        return SCRIPT_DIR
    if stage == "ui":
        return FRONTEND_DIR
    raise ValueError(f"Unknown production hub verification stage: {stage}")


def _run_stage_process(
    *,
    stage: str,
    base_url: str,
    verification_run_id: str | None = None,
) -> int:
    result = subprocess.run(
        _resolve_stage_command(
            stage=stage,
            base_url=base_url,
            verification_run_id=verification_run_id,
        ),
        cwd=_resolve_stage_cwd(stage),
        check=False,
    )
    return int(result.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        requested_stages = _select_stages(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    base_url = str(args.base_url or "").rstrip("/")
    continue_on_failure = bool(args.continue_on_failure)
    stage_exit_codes: dict[str, int | None] = {stage: None for stage in STAGE_ORDER}
    stage_durations: dict[str, str] = {stage: "" for stage in STAGE_ORDER}
    stage_duration_secs: dict[str, float] = {stage: 0.0 for stage in STAGE_ORDER}
    stage_error_summaries: dict[str, str] = {stage: "" for stage in STAGE_ORDER}
    completed_stages: list[str] = []
    failed_stage = ""
    failure_detail = ""
    suite_start = time.monotonic()
    started_at = _utc_now_iso()
    verification_run_id = str(uuid.uuid4())

    for stage in requested_stages:
        stage_start = time.monotonic()
        exit_code = _run_stage_process(
            stage=stage,
            base_url=base_url,
            verification_run_id=verification_run_id if stage == "smoke" else None,
        )

        stage_exit_codes[stage] = exit_code
        stage_duration_secs[stage] = time.monotonic() - stage_start
        stage_durations[stage] = _format_duration(stage_duration_secs[stage])
        completed_stages.append(stage)

        if exit_code != 0:
            if not failed_stage:
                failed_stage = stage
                failure_detail = f"stage {stage} exited with code {exit_code}"
            stage_error_summaries[stage] = f"stage {stage} exited with code {exit_code}"
            if not continue_on_failure:
                break

    overall_success = (
        len(completed_stages) == len(requested_stages)
        and all(stage_exit_codes[stage] == 0 for stage in requested_stages)
    )
    finished_at = _utc_now_iso()

    summary: dict[str, Any] = {
        "suite_mode": "production_hub_verification",
        "base_url": base_url,
        "verification_run_id": verification_run_id,
        "stages_requested": ",".join(requested_stages),
        "stages_completed": ",".join(completed_stages),
        "failed_stage": failed_stage,
        "continue_on_failure": continue_on_failure,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    for stage in STAGE_ORDER:
        summary[f"stage_{stage}_exit_code"] = (
            "" if stage_exit_codes[stage] is None else stage_exit_codes[stage]
        )
        summary[f"stage_{stage}_duration_sec"] = stage_durations[stage]
    summary["overall_success"] = overall_success
    summary["total_duration_sec"] = _format_duration(time.monotonic() - suite_start)

    for key, value in summary.items():
        _print_marker(key, value)

    payload: dict[str, Any] = {
        "id": verification_run_id,
        "run_mode": (
            "smoke_only"
            if args.smoke_only
            else "ui_only"
            if args.ui_only
            else "suite"
        ),
        "status": "completed" if overall_success else "failed",
        "overall_success": overall_success,
        "failure_stage": None if not failed_stage else failed_stage,
        "error_summary": None if not failure_detail else failure_detail,
        "base_url": base_url,
        "total_duration_sec": round(time.monotonic() - suite_start, 3),
        "started_at": started_at,
        "finished_at": finished_at,
        "stage_status": {
            stage: {
                "status": (
                    "skipped"
                    if stage_exit_codes[stage] is None
                    else "passed"
                    if stage_exit_codes[stage] == 0
                    else "failed"
                ),
                **(
                    {"duration_sec": round(stage_duration_secs[stage], 3)}
                    if stage_exit_codes[stage] is not None
                    else {}
                ),
                **(
                    {"error_summary": stage_error_summaries[stage]}
                    if stage_exit_codes[stage] not in {None, 0}
                    else {}
                ),
            }
            for stage in STAGE_ORDER
        },
    }

    persistence_ok = False
    try:
        response = _post_json(
            f"{base_url}/api/v1/production/verification/runs",
            payload,
        )
    except Exception as exc:  # pragma: no cover - exercised in tests
        print("production_verification_run_persisted: false")
        print(f"production_verification_run_persist_error: {exc}")
    else:
        persistence_ok = True
        print("production_verification_run_persisted: true")
        run_id = response.get("id")
        if run_id:
            print(f"production_verification_run_id: {run_id}")

    return 0 if overall_success and persistence_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
