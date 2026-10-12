#!/usr/bin/env bash
# Render's free tier allows one web service, so the agent and the API-plus-worker share it
# (specs/features/free-hosting.md). If either exits, the other is stopped and Render restarts the service.
set -uo pipefail

# Long enough for a cold start on 0.1 CPU; the agent starts anyway after it.
API_WAIT_SECONDS=300

# Waits for both: a send in flight records its outcome before the container goes.
stop_all() {
  kill $(jobs -p) 2>/dev/null
  wait
}
trap 'stop_all; exit 0' TERM INT

python -m app.combined &
# The API first: it answers Render's health check, and the two splitting 0.1 CPU slowed both.
python - "$API_WAIT_SECONDS" <<'PY'
import os, sys, time, urllib.request
deadline = time.monotonic() + int(sys.argv[1])
while time.monotonic() < deadline:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{os.environ['PORT']}/healthz", timeout=2)
        break
    except OSError:
        time.sleep(1)
PY
uvicorn email_agent:app --host 127.0.0.1 --port 8001 --no-access-log &
wait -n
stop_all
exit 1
