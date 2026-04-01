from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_ops_pilot_baseline.py"
    spec = importlib.util.spec_from_file_location("run_ops_pilot_baseline", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_baseline_section_includes_all_expected_lines() -> None:
    module = _load_module()

    results = [
        module.CheckResult(
            name="backend tests",
            status="PASS",
            summary="5 files / 62 passed",
            details="",
            duration_sec=3.5,
        ),
        module.CheckResult(
            name="frontend tests",
            status="PASS",
            summary="vitest ok",
            details="",
            duration_sec=8.2,
        ),
        module.CheckResult(
            name="adult provider resolution",
            status="PASS",
            summary="prompt=adult_openrouter_grok runtime=adult_local_llm",
            details="",
            duration_sec=0.1,
        ),
        module.CheckResult(
            name="story planner smoke",
            status="FAIL",
            summary="lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=0",
            details="connection refused",
            duration_sec=1.2,
        ),
    ]

    rendered = module._render_baseline_section(results)

    assert rendered.splitlines() == [
        "## Baseline",
        "- backend tests: PASS - 5 files / 62 passed",
        "- frontend tests: PASS - vitest ok",
        "- adult provider resolution: PASS - prompt=adult_openrouter_grok runtime=adult_local_llm",
        "- story planner smoke: FAIL - lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=0",
    ]


def test_write_baseline_section_dry_run_does_not_modify_file(tmp_path: Path) -> None:
    module = _load_module()

    log_path = tmp_path / "pilot-log.md"
    log_path.write_text(
        "# HollowForge Ops Pilot Log\n\n"
        "## Baseline\n"
        "- backend tests:\n"
        "- frontend tests:\n"
        "- adult provider resolution:\n"
        "- story planner smoke:\n",
        encoding="utf-8",
    )

    original = log_path.read_text(encoding="utf-8")
    preview = module._write_baseline_section(
        log_path=log_path,
        rendered_baseline=(
            "## Baseline\n"
            "- backend tests: PASS - ok\n"
            "- frontend tests: PASS - ok\n"
            "- adult provider resolution: PASS - ok\n"
            "- story planner smoke: FAIL - offline\n"
        ),
        dry_run=True,
    )

    assert "PASS - ok" in preview
    assert log_path.read_text(encoding="utf-8") == original


def test_write_baseline_section_preserves_other_sections(tmp_path: Path) -> None:
    module = _load_module()

    log_path = tmp_path / "pilot-log.md"
    log_path.write_text(
        "# HollowForge Ops Pilot Log\n\n"
        "## Baseline\n"
        "- backend tests:\n"
        "- frontend tests:\n"
        "- adult provider resolution:\n"
        "- story planner smoke:\n\n"
        "## Episode Runs\n"
        "- episode:\n"
        "  - premise: keep-me\n\n"
        "## Ready Queue\n"
        "- selected generation ids: keep-me\n\n"
        "## Publishing Pilot\n"
        "- generation id: keep-me\n",
        encoding="utf-8",
    )

    module._write_baseline_section(
        log_path=log_path,
        rendered_baseline=(
            "## Baseline\n"
            "- backend tests: PASS - ok\n"
            "- frontend tests: PASS - ok\n"
            "- adult provider resolution: PASS - ok\n"
            "- story planner smoke: FAIL - offline\n"
        ),
        dry_run=False,
    )

    updated = log_path.read_text(encoding="utf-8")
    assert "- backend tests: PASS - ok" in updated
    assert "premise: keep-me" in updated
    assert "selected generation ids: keep-me" in updated
    assert "generation id: keep-me" in updated
