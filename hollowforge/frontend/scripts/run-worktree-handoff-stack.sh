#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${FRONTEND_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"

DRY_RUN=0
OPEN_BROWSER=0

HOST="${HOLLOWFORGE_DEV_HOST:-127.0.0.1}"
BACKEND_PORT="${HOLLOWFORGE_ALT_BACKEND_PORT:-8014}"
FRONTEND_PORT="${HOLLOWFORGE_ALT_FRONTEND_PORT:-4173}"
ANIMATION_REMOTE_BASE_URL="${HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL:-http://127.0.0.1:8600}"
BACKEND_URL="http://${HOST}:${BACKEND_PORT}"
FRONTEND_URL="http://${HOST}:${FRONTEND_PORT}"
BROWSER_URL="${FRONTEND_URL}/production"

PROJECT_PARENT="$(cd "${REPO_ROOT}/../../.." && pwd)"
SHARED_BACKEND_PYTHON="${PROJECT_PARENT}/hollowforge/backend/.venv/bin/python"

print_usage() {
  cat <<EOF
Usage: ./scripts/run-worktree-handoff-stack.sh [--dry-run] [--open-browser] [--help]

Options:
  --dry-run       Print the resolved stack targets and exit.
  --open-browser  Open ${BROWSER_URL} after the stack starts.
  --help          Show this help text and exit.
EOF
}

while (($# > 0)); do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --open-browser)
      OPEN_BROWSER=1
      ;;
    --help|-h)
      print_usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      print_usage >&2
      exit 1
      ;;
  esac
  shift
done

resolve_backend_python() {
  local candidate=""

  for candidate in \
    "${HOLLOWFORGE_BACKEND_PYTHON:-}" \
    "${BACKEND_DIR}/.venv/bin/python" \
    "${SHARED_BACKEND_PYTHON}"
  do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  echo "[ERROR] No usable backend Python found." >&2
  echo "Checked:" >&2
  echo "  - HOLLOWFORGE_BACKEND_PYTHON" >&2
  echo "  - ${BACKEND_DIR}/.venv/bin/python" >&2
  echo "  - ${SHARED_BACKEND_PYTHON}" >&2
  return 1
}

assert_port_free() {
  local port="$1"
  if nc -z "${HOST}" "${port}" >/dev/null 2>&1; then
    echo "[ERROR] ${HOST}:${port} is already in use." >&2
    return 1
  fi
}

open_browser_target() {
  if command -v open >/dev/null 2>&1; then
    open "${BROWSER_URL}" >/dev/null 2>&1 &
    return 0
  fi

  echo "[WARN] 'open' command not found; browser launch skipped." >&2
  return 0
}

BACKEND_PYTHON="$(resolve_backend_python)"
assert_port_free "${BACKEND_PORT}"
assert_port_free "${FRONTEND_PORT}"

echo "[INFO] Starting HollowForge worktree handoff stack"
echo "[INFO] Backend:  ${BACKEND_URL}"
echo "[INFO] Frontend: ${FRONTEND_URL}"
echo "[INFO] Backend Python: ${BACKEND_PYTHON}"

if [[ "${OPEN_BROWSER}" -eq 1 ]]; then
  echo "[INFO] Browser:  ${BROWSER_URL}"
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[INFO] Dry run only; stack was not started."
  exit 0
fi

backend_pid=""
frontend_pid=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  if [[ -n "${frontend_pid}" ]] && kill -0 "${frontend_pid}" >/dev/null 2>&1; then
    kill "${frontend_pid}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${backend_pid}" ]] && kill -0 "${backend_pid}" >/dev/null 2>&1; then
    kill "${backend_pid}" >/dev/null 2>&1 || true
  fi

  wait "${frontend_pid}" 2>/dev/null || true
  wait "${backend_pid}" 2>/dev/null || true

  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

(
  cd "${BACKEND_DIR}"
  env \
    HOLLOWFORGE_PUBLIC_API_BASE_URL="${BACKEND_URL}" \
    HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL="${ANIMATION_REMOTE_BASE_URL}" \
    "${BACKEND_PYTHON}" -m uvicorn app.main:app --host "${HOST}" --port "${BACKEND_PORT}"
) &
backend_pid=$!

(
  cd "${FRONTEND_DIR}"
  env \
    HOLLOWFORGE_DEV_PROXY_TARGET="${BACKEND_URL}" \
    npm run dev -- --host "${HOST}" --port "${FRONTEND_PORT}"
) &
frontend_pid=$!

echo "[INFO] Press Ctrl+C to stop both processes."

if [[ "${OPEN_BROWSER}" -eq 1 ]]; then
  open_browser_target
fi

while true; do
  if ! kill -0 "${backend_pid}" >/dev/null 2>&1; then
    wait "${backend_pid}"
    break
  fi
  if ! kill -0 "${frontend_pid}" >/dev/null 2>&1; then
    wait "${frontend_pid}"
    break
  fi
  sleep 1
done
