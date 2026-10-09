#!/usr/bin/env bash
# Starts the pinned Presidio containers from docker-compose.yml and waits until both answer /health.
# CI runs this instead of GitHub service containers, which fail the whole job the first time a
# container reports unhealthy, with no retry and no logs (the anonymizer did this on 2 of ~6 runs).
# The analyzer starts first: it loads spaCy models, and starting both at once slowed the anonymizer.
set -euo pipefail
cd "$(dirname "$0")/.."  # docker-compose.yml is at the repo root, whatever directory this runs from

WAIT_SECONDS=120
POLL_SECONDS=2

# A worker that accepts the connection but never answers (seen on GitHub runners) must count as a
# failed check, not hang the job: every probe has a time limit.
PROBE_SECONDS=5
healthy() { curl -fs --max-time "$PROBE_SECONDS" "http://127.0.0.1:$1/health" >/dev/null; }

# Waits for one service; restarts it once if it does not answer in time, then gives up with its logs.
start() {
  local service=$1 port=$2
  docker compose up -d "$service"
  for attempt in 1 2; do
    # Wall-clock deadline, not a count of tries: a try that times out takes PROBE_SECONDS longer.
    local deadline=$((SECONDS + WAIT_SECONDS))
    while [ "$SECONDS" -lt "$deadline" ]; do
      healthy "$port" && { echo "$service is healthy"; return 0; }
      sleep "$POLL_SECONDS"
    done
    echo "$service did not answer within ${WAIT_SECONDS}s (attempt $attempt)"
    [ "$attempt" = 1 ] && docker compose restart "$service"
  done
  docker compose logs "$service"
  return 1
}

start presidio-analyzer 5001
start presidio-anonymizer 5002
