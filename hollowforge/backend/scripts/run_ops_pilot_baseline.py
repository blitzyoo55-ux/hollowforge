from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(slots=True)
class CheckResult:
    name: str
    status: str
    summary: str
    details: str
    duration_sec: float


def _render_baseline_section(results: Sequence[CheckResult]) -> str:
    lines = ["## Baseline"]
    by_name = {result.name: result for result in results}
    for check_name in (
        "backend tests",
        "frontend tests",
        "adult provider resolution",
        "story planner smoke",
    ):
        result = by_name.get(check_name)
        if result is None:
            lines.append(f"- {check_name}:")
            continue
        lines.append(f"- {check_name}: {result.status} - {result.summary}")
    return "\n".join(lines) + "\n"


def _write_baseline_section(*, log_path: Path, rendered_baseline: str, dry_run: bool) -> str:
    original = log_path.read_text(encoding="utf-8")
    start_marker = "## Baseline\n"

    start = original.find(start_marker)
    if start == -1:
        raise ValueError("Baseline section not found")

    section_start = start + len(start_marker)
    section_end = original.find("\n## ", section_start)
    if section_end == -1:
        section_end = len(original)

    updated = original[:start] + rendered_baseline + original[section_end:]
    if not dry_run:
        log_path.write_text(updated, encoding="utf-8")
    return rendered_baseline
