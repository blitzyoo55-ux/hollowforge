# HollowForge Remote Access (No Tailscale)

This setup uses:
- `nginx` as public reverse proxy
- `oauth2-proxy` for Google sign-in
- existing HollowForge backend (`127.0.0.1:8000`)
- static frontend build (`frontend/dist`)

## 1) Prepare Google OAuth

1. In Google Cloud Console, create OAuth Client (Web application).
2. Add Authorized redirect URI:
   - `https://YOUR_DOMAIN/oauth2/callback`
3. Copy Client ID and Client Secret.

## 2) Prepare oauth2-proxy env

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/oauth2-proxy
cp .env.oauth2-proxy.example .env.oauth2-proxy
```

Fill `.env.oauth2-proxy`:
- `OAUTH2_PROXY_CLIENT_ID`
- `OAUTH2_PROXY_CLIENT_SECRET`
- `OAUTH2_PROXY_COOKIE_SECRET`
- `OAUTH2_PROXY_REDIRECT_URL`

Generate cookie secret example:

```bash
python3 - <<'PY'
import secrets, base64
print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="))
PY
```

## 3) Build frontend for nginx

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm run build
```

## 4) Install LaunchAgents

```bash
cp /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/launchd/com.mori.hollowforge.oauth2-proxy.plist ~/Library/LaunchAgents/
cp /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/launchd/com.mori.hollowforge.nginx.oauth.plist ~/Library/LaunchAgents/

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mori.hollowforge.oauth2-proxy.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mori.hollowforge.nginx.oauth.plist
launchctl kickstart -k gui/$(id -u)/com.mori.hollowforge.oauth2-proxy
launchctl kickstart -k gui/$(id -u)/com.mori.hollowforge.nginx.oauth
```

## 5) Ports and access

- nginx listens on `8080`
- oauth2-proxy listens on `127.0.0.1:4180`

For internet access, forward router port `443` to this Mac and terminate HTTPS at reverse proxy in front of `8080` (or run TLS directly on nginx config).

## 6) Logs

- nginx:
  - `backend/logs/nginx_access.log`
  - `backend/logs/nginx_error.log`
  - `backend/logs/nginx_launchd_stderr.log`
- oauth2-proxy:
  - `backend/logs/oauth2_proxy_launchd_stdout.log`
  - `backend/logs/oauth2_proxy_launchd_stderr.log`
