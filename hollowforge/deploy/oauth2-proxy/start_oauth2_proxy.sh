#!/bin/zsh
set -euo pipefail

BASE_DIR="/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/oauth2-proxy"
ENV_FILE="${BASE_DIR}/.env.oauth2-proxy"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy .env.oauth2-proxy.example and fill values."
  exit 1
fi

set -a
source "${ENV_FILE}"
set +a

required_vars=(
  OAUTH2_PROXY_CLIENT_ID
  OAUTH2_PROXY_CLIENT_SECRET
  OAUTH2_PROXY_COOKIE_SECRET
  OAUTH2_PROXY_REDIRECT_URL
)

for var in "${required_vars[@]}"; do
  if [[ -z "${(P)var:-}" ]]; then
    echo "Missing required variable: ${var}"
    exit 1
  fi
done

exec /opt/homebrew/opt/oauth2_proxy/bin/oauth2-proxy \
  --provider=google \
  --http-address=127.0.0.1:4180 \
  --reverse-proxy=true \
  --set-xauthrequest=true \
  --upstream=static://202 \
  --scope="openid email profile" \
  --skip-provider-button=true \
  --cookie-secure=true \
  --cookie-samesite=lax \
  --cookie-secret="${OAUTH2_PROXY_COOKIE_SECRET}" \
  --client-id="${OAUTH2_PROXY_CLIENT_ID}" \
  --client-secret="${OAUTH2_PROXY_CLIENT_SECRET}" \
  --redirect-url="${OAUTH2_PROXY_REDIRECT_URL}" \
  --email-domain="${OAUTH2_PROXY_EMAIL_DOMAIN:-*}"
