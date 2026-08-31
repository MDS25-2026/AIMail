#!/usr/bin/env bash
# Run all AImail services in one terminal with prefixed logs. Ctrl+C stops them all.
#
# Needs the shared .env, the venv (.venv), the frontend deps installed, docker (optional,
# for Presidio NER), and (for the listener) listener/credentials.json + token.json. See README.md.

set -uo pipefail
cd "$(dirname "$0")"

# Kill the whole process group on exit so no orphan uvicorn/vite/go children survive.
trap 'kill 0' EXIT INT TERM

# Presidio first so the analyzer's model load warms while the services boot. Not fatal:
# without it the listener degrades to regex-only masking by design. Not torn down on exit —
# the containers are idle-cheap and restart with Docker anyway.
docker compose up -d 2>/dev/null || echo "[presidio] unavailable — listener degrades to regex-only"

# Free stale ports first (the orphan problem). 8080 is left alone — other local projects use it;
# the dashboard is pinned to 8090.
fuser -k 8000/tcp 8001/tcp 8090/tcp 2>/dev/null || true

# fuser's kill is async; a dying orphan can still hold the socket when uvicorn binds,
# which kills the backend with "address already in use". Wait for actual release (max 5s).
for _ in $(seq 1 20); do
	ss -ltn | grep -qE ':(8000|8001|8090) ' || break
	sleep 0.25
done

( cd backend && ../.venv/bin/uvicorn app.main:app --reload 2>&1 | sed 's/^/[backend]  /' ) &
( cd backend && ../.venv/bin/uvicorn email_agent:app --reload --port 8001 2>&1 | sed 's/^/[agent]    /' ) &
( cd frontend/frontend/mail-clarity-dash-main && npm run dev -- --port 8090 --strictPort 2>&1 | sed 's/^/[web]      /' ) &
( cd listener && go run . 2>&1 | sed 's/^/[listener] /' ) &

wait
