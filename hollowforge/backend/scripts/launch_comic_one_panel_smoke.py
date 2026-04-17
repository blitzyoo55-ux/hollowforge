"""Run a fast one-panel comic smoke flow against a local backend."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import launch_comic_one_panel_verification as one_panel_verification
from comic_verification_profiles import SMOKE_PROFILE


def main() -> int:
    return one_panel_verification.main(profile=SMOKE_PROFILE)


if __name__ == "__main__":
    raise SystemExit(main())
