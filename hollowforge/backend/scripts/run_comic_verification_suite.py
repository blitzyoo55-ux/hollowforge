"""Run the approved comic verification suite from one operator-facing CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
STAGE_ORDER = ("smoke", "full", "remote")
STAGE_SCRIPTS = {
    "smoke": "launch_comic_one_panel_smoke.py",
    "full": "launch_comic_one_panel_verification.py",
    "remote": "launch_comic_remote_render_smoke.py",
}


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
    parser.add_argument("--full-only", action="store_true")
    parser.add_argument("--remote-only", action="store_true")
    parser.add_argument("--continue-on-failure", action="store_true")
    return parser


def _select_stages(args: argparse.Namespace) -> list[str]:
    selected = [
        stage
        for stage, enabled in (
            ("smoke", args.smoke_only),
            ("full", args.full_only),
            ("remote", args.remote_only),
        )
        if enabled
    ]
    if len(selected) > 1:
        raise ValueError("choose only one stage selection flag")
    return selected or list(STAGE_ORDER)


def _resolve_stage_script_path(stage: str) -> Path:
    return SCRIPT_DIR / STAGE_SCRIPTS[stage]


def _run_stage_process(*, stage: str, script_path: Path, base_url: str) -> int:
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--base-url",
            base_url,
        ],
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
    missing_stage_script = ""
    failure_detail = ""
    suite_start = time.monotonic()
    started_at = _utc_now_iso()

    for stage in requested_stages:
        stage_start = time.monotonic()
        script_path = _resolve_stage_script_path(stage)

        if not script_path.exists():
            exit_code = 1
            if not missing_stage_script:
                missing_stage_script = stage
        else:
            exit_code = _run_stage_process(
                stage=stage,
                script_path=script_path,
                base_url=base_url,
            )

        stage_exit_codes[stage] = exit_code
        stage_duration_secs[stage] = time.monotonic() - stage_start
        stage_durations[stage] = _format_duration(stage_duration_secs[stage])
        completed_stages.append(stage)

        if exit_code != 0:
            if not failed_stage:
                failed_stage = stage
                failure_detail = (
                    f"stage {stage} script is missing"
                    if not script_path.exists()
                    else f"stage {stage} exited with code {exit_code}"
                )
            stage_error_summaries[stage] = (
                f"stage {stage} script is missing"
                if not script_path.exists()
                else f"stage {stage} exited with code {exit_code}"
            )
            if not continue_on_failure:
                break

    total_duration = _format_duration(time.monotonic() - suite_start)
    overall_success = (
        len(completed_stages) == len(requested_stages)
        and all(stage_exit_codes[stage] == 0 for stage in requested_stages)
    )

    summary: dict[str, Any] = {
        "suite_mode": "comic_verification",
        "base_url": base_url,
        "stages_requested": ",".join(requested_stages),
        "stages_completed": ",".join(completed_stages),
        "failed_stage": failed_stage,
        "missing_stage_script": missing_stage_script,
        "continue_on_failure": continue_on_failure,
    }
    for stage in STAGE_ORDER:
        summary[f"stage_{stage}_exit_code"] = (
            "" if stage_exit_codes[stage] is None else stage_exit_codes[stage]
        )
        summary[f"stage_{stage}_duration_sec"] = stage_durations[stage]
    summary["overall_success"] = overall_success
    summary["total_duration_sec"] = total_duration

    for key, value in summary.items():
        _print_marker(key, value)

    finished_at = _utc_now_iso()
    payload: dict[str, Any] = {
        "run_mode": (
            "full_only"
            if args.full_only
            else "remote_only"
            if args.remote_only
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
            f"{base_url}/api/v1/production/comic-verification/runs",
            payload,
        )
    except Exception as exc:  # pragma: no cover - exercised in tests
        print("comic_verification_run_persisted: false")
        print(f"comic_verification_run_persist_error: {exc}")
    else:
        persistence_ok = True
        print("comic_verification_run_persisted: true")
        run_id = response.get("id")
        if run_id:
            print(f"comic_verification_run_id: {run_id}")

    return 0 if overall_success and persistence_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
