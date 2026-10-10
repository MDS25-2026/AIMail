# infra

How AImail runs: what is local, what is hosted, what ships as an image, and how each is checked.

## The pieces

| Piece | Where it runs | Built from | Probes |
|-------|---------------|------------|--------|
| Database | Supabase Postgres with `pgvector` (hosted) | `backend/app/db/migrations/` | — |
| Backend API (`:8000`) | `make dev`, or the backend image | `backend/Dockerfile` | `/healthz`, `/readyz` (database) |
| Agent (`:8001`) | `make dev`, or the backend image with `APP=email_agent:app PORT=8001` | `backend/Dockerfile` | `/healthz`, `/readyz` (model configured) |
| Worker | `make worker` (started by `make dev`) | the backend code | — |
| Listener | `make dev`, or its image | `listener/Dockerfile` | `:8095/healthz`, `:8095/readyz` |
| Presidio analyzer `:5001`, anonymizer `:5002`, attachment reader `:5003` | `docker compose up -d` at the repo root, bound to `127.0.0.1` | images pinned by digest in `docker-compose.yml` | `/health` |
| Dashboard (`:8090`) | `make web` (started by `make dev`) | `frontend/frontend/mail-clarity-dash-main/` | — |

The agent has no token of its own outside dev: a deployed environment refuses to start without
`AGENT_TOKEN`, and the backend sends it on every call (`app/core/agent_auth.py`).

## Database

- Apply migrations with `make migrate` (or `python scripts/migrate.py` in the backend image). They
  are recorded in `schema_migrations` with a checksum, run under an advisory lock, and an edited
  applied migration stops the run. `python scripts/migrate.py --status` lists what is pending.
- Every public table has row-level security on; CI checks this on a fresh database.
- CI's `database` job applies every migration twice to a pgvector container and runs
  `backend/tests/test_database.py` (RLS, the append-only audit chain, atomic rate counters). Run it
  locally against a throwaway container only:

  ```bash
  docker run -d --rm --name aimail-pg -e POSTGRES_PASSWORD=test -p 127.0.0.1:55491:5432 pgvector/pgvector:pg16
  cd backend && DATABASE_URL=postgresql://postgres:test@127.0.0.1:55491/postgres AIMAIL_ENV_FILE= ../.venv/bin/python scripts/migrate.py
  TEST_DATABASE_URL=postgresql://postgres:test@127.0.0.1:55491/postgres ../.venv/bin/pytest -q tests/test_database.py
  ```

CI's `listener` job starts Presidio with `infra/start-presidio.sh` (the same compose services, analyzer first,
one restart if it does not answer within two minutes, its logs on failure) and runs the masking recall gate
against it.

## Configuration

Every setting is in the repo-root [`.env.example`](../.env.example), with what it does. Images read
the environment only (`AIMAIL_ENV_FILE` is empty in them), log JSON (`LOG_FORMAT=json`), and outside
`ENVIRONMENT=dev` refuse to start with a missing secret or a localhost public URL.

## Gmail notifications

Pub/Sub holds Gmail's notifications on a pull subscription the listener reads. Set up the dead-letter policy with
[`pubsub-dead-letter.md`](pubsub-dead-letter.md).

## Not here yet

No infrastructure-as-code and no chosen host. The images and probes above are what a host needs; the
cookie and CORS layout for a deployed dashboard is proposed in [ADR 0007](../docs/adr/0007-one-site-for-the-dashboard-and-api.md): one site, two subdomains.
