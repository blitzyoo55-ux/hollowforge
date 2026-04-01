"""Sync publish-safe runtime env keys from the canonical backend .env."""

from __future__ import annotations

import argparse
from pathlib import Path

ALLOWED_KEYS = (
    "OPENROUTER_API_KEY",
    "MARKETING_PROVIDER_NAME",
    "MARKETING_MODEL",
    "MARKETING_PROMPT_VERSION",
    "HOLLOWFORGE_PUBLIC_API_BASE_URL",
)

DEFAULT_SOURCE_ENV = Path(
    "/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.env"
)
DEFAULT_TARGET_ENV = Path(__file__).resolve().parents[1] / ".env"


def _parse_simple_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        values[key] = value.strip()
    return values


def _render_allowed_env(values: dict[str, str]) -> str:
    lines = []
    for key in ALLOWED_KEYS:
        if key in values:
            lines.append(f"{key}={values[key]}")
    return "\n".join(lines) + ("\n" if lines else "")


def _print_status(values: dict[str, str]) -> None:
    for key in ALLOWED_KEYS:
        status = "present" if key in values else "missing"
        print(f"{key}={status}")


def sync_runtime_env(
    *,
    source_env: Path = DEFAULT_SOURCE_ENV,
    target_env: Path = DEFAULT_TARGET_ENV,
    dry_run: bool = False,
    print_status: bool = False,
) -> int:
    if not source_env.exists():
        print(f"missing source env: {source_env}", flush=True)
        return 1

    source_values = _parse_simple_env_file(source_env)
    allowed_values = {
        key: source_values[key]
        for key in ALLOWED_KEYS
        if key in source_values
    }

    if print_status:
        _print_status(source_values)

    if not dry_run:
        target_env.write_text(_render_allowed_env(allowed_values), encoding="utf-8")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-env", type=Path, default=DEFAULT_SOURCE_ENV)
    parser.add_argument("--target-env", type=Path, default=DEFAULT_TARGET_ENV)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-status", action="store_true")
    args = parser.parse_args(argv)
    return sync_runtime_env(
        source_env=args.source_env,
        target_env=args.target_env,
        dry_run=args.dry_run,
        print_status=args.print_status,
    )


if __name__ == "__main__":
    raise SystemExit(main())
