"""Run the bounded stale animation reconciliation helper against a local backend."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.animation_reconciliation_service import reconcile_stale_animation_jobs


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
LOCAL_BACKEND_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}


def _is_local_backend_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    scheme = (parsed.scheme or "").strip().lower()
    hostname = (parsed.hostname or "").strip().lower()
    return scheme in {"http", "https"} and hostname in LOCAL_BACKEND_HOSTNAMES


def _print_summary(summary: dict[str, int]) -> None:
    for key in (
        "checked",
        "updated",
        "failed_restart",
        "completed",
        "cancelled",
        "skipped_unreachable",
    ):
        print(f"{key}: {int(summary.get(key) or 0)}")


async def _run_reconciliation() -> dict[str, int]:
    return await reconcile_stale_animation_jobs()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    try:
        if not _is_local_backend_url(args.base_url):
            raise RuntimeError(
                "reconcile_stale_animation_jobs only supports local backend URLs"
            )

        summary = asyncio.run(_run_reconciliation())
        _print_summary(summary)
        return 0
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
