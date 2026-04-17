#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_GIT_DIR="$(git -C "${SCRIPT_DIR}" rev-parse --git-common-dir)"
COMMON_REPO_ROOT="$(cd "$(dirname "${COMMON_GIT_DIR}")" && pwd)"
COMMON_PROJECT_DIR="${COMMON_REPO_ROOT}/hollowforge"

if [[ -x "${SCRIPT_DIR}/.venv/bin/python" ]]; then
  PYTHON_BIN="${SCRIPT_DIR}/.venv/bin/python"
elif [[ -x "${COMMON_PROJECT_DIR}/backend/.venv/bin/python" ]]; then
  PYTHON_BIN="${COMMON_PROJECT_DIR}/backend/.venv/bin/python"
else
  echo "[ERROR] Missing backend venv in worktree or common project." >&2
  exit 1
fi

: "${HOLLOWFORGE_BACKEND_HOST:=127.0.0.1}"
: "${HOLLOWFORGE_BACKEND_PORT:=8000}"
: "${HOLLOWFORGE_ANIMATION_EXECUTOR_MODE:=remote_worker}"
: "${HOLLOWFORGE_ANIMATION_EXECUTOR_KEY:=local_animation_worker}"
: "${HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL:=http://127.0.0.1:8600}"
: "${HOLLOWFORGE_PUBLIC_API_BASE_URL:=http://${HOLLOWFORGE_BACKEND_HOST}:${HOLLOWFORGE_BACKEND_PORT}}"
export HOLLOWFORGE_BACKEND_HOST
export HOLLOWFORGE_BACKEND_PORT
export HOLLOWFORGE_ANIMATION_EXECUTOR_MODE
export HOLLOWFORGE_ANIMATION_EXECUTOR_KEY
export HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL
export HOLLOWFORGE_PUBLIC_API_BASE_URL

cd "${SCRIPT_DIR}"
exec "${PYTHON_BIN}" -m uvicorn app.main:app --host "${HOLLOWFORGE_BACKEND_HOST}" --port "${HOLLOWFORGE_BACKEND_PORT}"
