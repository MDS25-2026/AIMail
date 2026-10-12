#!/usr/bin/env bash
# Render's free tier allows one web service, so the agent and the API-plus-worker share it
# (specs/features/free-hosting.md). If either exits, the other is stopped and Render restarts the service.
set -uo pipefail

# Waits for both: a send in flight records its outcome before the container goes.
stop_all() {
  kill $(jobs -p) 2>/dev/null
  wait
}
trap 'stop_all; exit 0' TERM INT

uvicorn email_agent:app --host 127.0.0.1 --port 8001 --no-access-log &
python -m app.combined &
wait -n
stop_all
exit 1
