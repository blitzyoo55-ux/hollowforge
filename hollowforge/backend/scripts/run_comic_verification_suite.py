"""Run the approved comic verification suite from one operator-facing CLI."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


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
    completed_stages: list[str] = []
    failed_stage = ""
    missing_stage_script = ""
    suite_start = time.monotonic()

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
        stage_durations[stage] = _format_duration(time.monotonic() - stage_start)
        completed_stages.append(stage)

        if exit_code != 0:
            if not failed_stage:
                failed_stage = stage
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

    return 0 if overall_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
