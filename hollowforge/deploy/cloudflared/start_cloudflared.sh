#!/bin/zsh
set -euo pipefail

BASE_DIR="/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/cloudflared"
ENV_FILE="${BASE_DIR}/.env.cloudflared"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy .env.cloudflared.example and set tunnel token."
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

if [[ -z "${CLOUDFLARED_TUNNEL_TOKEN:-}" ]]; then
  echo "Missing CLOUDFLARED_TUNNEL_TOKEN"
  exit 1
fi

TOKEN="${CLOUDFLARED_TUNNEL_TOKEN}"
unset CLOUDFLARED_TUNNEL_TOKEN

exec /opt/homebrew/opt/cloudflared/bin/cloudflared tunnel run --token "${TOKEN}"
