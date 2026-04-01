from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import sync_runtime_env as sync_module


def _run_sync_runtime_env(
    *,
    source_path: Path,
    target_path: Path,
    dry_run: bool = False,
    print_status: bool = False,
) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        str(Path(sync_module.__file__).resolve()),
        "--source-env",
        str(source_path),
        "--target-env",
        str(target_path),
    ]
    if dry_run:
        args.append("--dry-run")
    if print_status:
        args.append("--print-status")
    return subprocess.run(args, capture_output=True, text=True)


def test_sync_runtime_env_copies_only_allowlisted_keys(tmp_path: Path) -> None:
    source_path = tmp_path / ".env.source"
    target_path = tmp_path / ".env.target"
    source_path.write_text(
        "\n".join(
            [
                "OPENROUTER_API_KEY=present",
                "MARKETING_PROVIDER_NAME=openrouter",
                "MARKETING_MODEL=grok-4.1",
                "MARKETING_PROMPT_VERSION=lab451_social_v1",
                "HOLLOWFORGE_PUBLIC_API_BASE_URL=https://example.invalid",
                "UNRELATED_SECRET=should-not-copy",
            ]
        ),
        encoding="utf-8",
    )

    completed = _run_sync_runtime_env(
        source_path=source_path,
        target_path=target_path,
        print_status=True,
    )

    assert completed.returncode == 0, completed.stderr
    printed_status = completed.stdout
    target_contents = target_path.read_text(encoding="utf-8")

    assert "OPENROUTER_API_KEY=present" in printed_status
    assert "MARKETING_PROVIDER_NAME=present" in printed_status
    assert "MARKETING_MODEL=present" in printed_status
    assert "MARKETING_PROMPT_VERSION=present" in printed_status
    assert "HOLLOWFORGE_PUBLIC_API_BASE_URL=present" in printed_status
    assert "UNRELATED_SECRET" not in target_contents


def test_sync_runtime_env_dry_run_does_not_write_target(tmp_path: Path) -> None:
    source_path = tmp_path / ".env.source"
    target_path = tmp_path / ".env.target"
    source_path.write_text("OPENROUTER_API_KEY=present\n", encoding="utf-8")

    completed = _run_sync_runtime_env(
        source_path=source_path,
        target_path=target_path,
        dry_run=True,
        print_status=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert not target_path.exists()


def test_sync_runtime_env_fails_when_source_env_missing(tmp_path: Path) -> None:
    source_path = tmp_path / ".env.missing"
    target_path = tmp_path / ".env.target"

    completed = _run_sync_runtime_env(
        source_path=source_path,
        target_path=target_path,
        print_status=True,
    )

    assert completed.returncode == 1
