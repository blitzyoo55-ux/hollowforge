#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[ERROR] Missing backend venv: ${PYTHON_BIN}" >&2
  exit 1
fi

: "${HOLLOWFORGE_ANIMATION_EXECUTOR_MODE:=remote_worker}"
: "${HOLLOWFORGE_ANIMATION_EXECUTOR_KEY:=local_animation_worker}"
: "${HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL:=http://127.0.0.1:8600}"
: "${HOLLOWFORGE_PUBLIC_API_BASE_URL:=http://127.0.0.1:8000}"
export HOLLOWFORGE_ANIMATION_EXECUTOR_MODE
export HOLLOWFORGE_ANIMATION_EXECUTOR_KEY
export HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL
export HOLLOWFORGE_PUBLIC_API_BASE_URL

cd "${SCRIPT_DIR}"
exec "${PYTHON_BIN}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
