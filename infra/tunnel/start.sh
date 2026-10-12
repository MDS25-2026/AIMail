#!/usr/bin/env bash
# make tunnel: Presidio for the backend on Render, behind Caddy's basic auth and a Cloudflare quick
# tunnel (specs/features/free-hosting.md). Prints the address for Render's PRESIDIO_ANALYZER_URL.
set -euo pipefail
cd "$(dirname "$0")/../.."

CADDY_IMAGE="caddy@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f"
WAIT_SECONDS=60

# One setting from .env, never echoed.
setting() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- || true; }

user=$(setting PRESIDIO_USER)
password=$(setting PRESIDIO_PASSWORD)
if [ -z "$user" ] || [ -z "$password" ]; then
  echo "Set PRESIDIO_USER and PRESIDIO_PASSWORD in .env, the same values as on Render." >&2
  exit 1
fi

# The password goes to Caddy on stdin, so it never appears in a process list.
PRESIDIO_PASSWORD_HASH=$(printf '%s\n' "$password" | docker run -i --rm "$CADDY_IMAGE" caddy hash-password)
export PRESIDIO_USER="$user" PRESIDIO_PASSWORD_HASH
docker compose --profile tunnel up -d --force-recreate presidio-analyzer presidio-gate presidio-tunnel

for _ in $(seq "$WAIT_SECONDS"); do
  address=$(docker logs presidio-tunnel 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)
  if [ -n "$address" ]; then
    echo "Set PRESIDIO_ANALYZER_URL on Render to: $address/analyze"
    echo "The address changes each time the tunnel starts. Stop it with: docker compose --profile tunnel stop presidio-gate presidio-tunnel"
    exit 0
  fi
  sleep 1
done
echo "The tunnel gave no address within ${WAIT_SECONDS}s; see: docker logs presidio-tunnel" >&2
exit 1
