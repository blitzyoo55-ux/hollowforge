# HollowForge Ultimate Remote Access (Cloudflare Zero Trust)

This is the recommended secure setup:
- No inbound port forwarding on home router
- Google SSO + policy enforcement at Cloudflare Access
- Tunnel from Mac mini to Cloudflare edge

## 1) Build frontend

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm run build
```

## 2) Start local reverse proxy (nginx on localhost:8080)

Config file:
- `deploy/nginx/nginx.cloudflare.conf`

Local check:

```bash
/opt/homebrew/opt/nginx/bin/nginx -t -c /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/nginx/nginx.cloudflare.conf
```

## 3) Create Cloudflare Tunnel (dashboard path)

1. Cloudflare Zero Trust dashboard -> Networks -> Tunnels -> Create Tunnel.
2. Choose Cloudflared.
3. Add Public Hostname:
   - Hostname: `hollowforge.your-domain.com`
   - Service type: HTTP
   - URL: `http://localhost:8080`
4. Copy tunnel token.

## 4) Configure cloudflared token on Mac

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/cloudflared
cp .env.cloudflared.example .env.cloudflared
# set CLOUDFLARED_TUNNEL_TOKEN
```

## 5) Configure Cloudflare Access policy

Zero Trust -> Access -> Applications:
1. Add application for `hollowforge.your-domain.com`
2. Identity provider: Google
3. Policy: allow only your email(s) or domain
4. Require MFA
5. Set reasonable session duration (e.g. 8h)

## 6) Install launchd services

```bash
cp /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/launchd/com.mori.hollowforge.nginx.cloudflare.plist ~/Library/LaunchAgents/
cp /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/deploy/launchd/com.mori.hollowforge.cloudflared.plist ~/Library/LaunchAgents/

launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mori.hollowforge.nginx.cloudflare.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.mori.hollowforge.cloudflared.plist

launchctl kickstart -k gui/$(id -u)/com.mori.hollowforge.nginx.cloudflare
launchctl kickstart -k gui/$(id -u)/com.mori.hollowforge.cloudflared
```

## 7) Verify

- Open: `https://hollowforge.your-domain.com`
- You should be redirected to Google login first.

## Worker callback note

If you use this protected hostname as `HOLLOWFORGE_PUBLIC_API_BASE_URL`, remote
workers cannot post callbacks through it with a plain bearer callback token
alone. Cloudflare Access will redirect unauthenticated worker requests to the
login flow unless you either:

- bypass Access for the callback path, or
- give the worker a Cloudflare Access service token and send
  `CF-Access-Client-Id` plus `CF-Access-Client-Secret` on callback requests

Worker env mapping:
- `WORKER_CF_ACCESS_CLIENT_ID=<service token client id>`
- `WORKER_CF_ACCESS_CLIENT_SECRET=<service token client secret>`

## Logs

- Nginx:
  - `backend/logs/nginx_cloudflare_access.log`
  - `backend/logs/nginx_cloudflare_error.log`
  - `backend/logs/nginx_cloudflare_launchd_stderr.log`
- Cloudflared:
  - `backend/logs/cloudflared_launchd_stdout.log`
  - `backend/logs/cloudflared_launchd_stderr.log`
