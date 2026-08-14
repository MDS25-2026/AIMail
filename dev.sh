#!/usr/bin/env bash
# Run all AImail services in one terminal with prefixed logs. Ctrl+C stops them all.
#
# Needs the shared .env, the venv (.venv), the frontend deps installed, and (for the listener)
# listener/credentials.json + token.json. See README.md.

set -uo pipefail
cd "$(dirname "$0")"

# Kill the whole process group on exit so no orphan uvicorn/vite/go children survive.
trap 'kill 0' EXIT INT TERM

# Free stale ports first (the orphan problem).
fuser -k 8000/tcp 8001/tcp 8080/tcp 8081/tcp 8082/tcp 2>/dev/null || true

( cd backend && ../.venv/bin/uvicorn app.main:app --reload 2>&1 | sed 's/^/[backend]  /' ) &
( cd backend && ../.venv/bin/uvicorn email_agent:app --reload --port 8001 2>&1 | sed 's/^/[agent]    /' ) &
( cd frontend/frontend/mail-clarity-dash-main && npm run dev 2>&1 | sed 's/^/[web]      /' ) &
( cd listener && go run . 2>&1 | sed 's/^/[listener] /' ) &

wait
