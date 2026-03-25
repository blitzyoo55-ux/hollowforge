#!/usr/bin/env python3
"""Dispatch one local LTXV animation job after the image queue becomes idle."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "hollowforge.db"
DEFAULT_API_BASE = os.getenv("HOLLOWFORGE_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")


def _active_generation_count(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        "SELECT COUNT(*) FROM generations WHERE status IN ('queued', 'running')"
    )
    return int(cursor.fetchone()[0] or 0)


def _latest_completed_generation_id(conn: sqlite3.Connection) -> str | None:
    cursor = conn.execute(
        """
        SELECT id
        FROM generations
        WHERE status = 'completed'
          AND image_path IS NOT NULL
          AND image_path != ''
        ORDER BY completed_at DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return str(row[0])


def _launch_ltxv(api_base: str, generation_id: str) -> int:
    payload = json.dumps(
        {
            "generation_id": generation_id,
            "dispatch_immediately": True,
        },
        ensure_ascii=False,
    )
    cmd = [
        "curl",
        "-sS",
        "-X",
        "POST",
        "-H",
        "Content-Type: application/json",
        "-d",
        payload,
        f"{api_base.rstrip('/')}/api/v1/animation/presets/ltxv_2b_fast/launch",
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout.strip())
    if completed.stderr:
        print(completed.stderr.strip(), file=sys.stderr)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation-id", default=None)
    parser.add_argument("--poll-sec", type=int, default=60)
    parser.add_argument("--max-wait-sec", type=int, default=0)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    try:
        generation_id = args.generation_id or _latest_completed_generation_id(conn)
        if not generation_id:
            print("No completed generation with image_path is available for LTXV launch.", file=sys.stderr)
            return 2

        waited = 0
        while True:
            active = _active_generation_count(conn)
            if active == 0:
                print(f"Queue idle. Dispatching ltxv_2b_fast for generation {generation_id}.")
                return _launch_ltxv(args.api_base, generation_id)

            print(f"Queue still active: {active} generation(s). Waiting {args.poll_sec}s.")
            time.sleep(args.poll_sec)
            waited += args.poll_sec
            if args.max_wait_sec > 0 and waited >= args.max_wait_sec:
                print("Timed out before queue became idle.", file=sys.stderr)
                return 3
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
