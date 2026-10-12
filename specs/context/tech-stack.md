# Tech stack

Pinned versions and where each pin lives. Update this file when a version is bumped. Python floors
are in `backend/requirements.txt`; the exact versions CI and the Docker image install are in
[`../../backend/constraints.txt`](../../backend/constraints.txt) (`pip install -r requirements.txt -c constraints.txt`).

## Backend and agent (`backend/`)

One image runs both: the API (`app.main:app`, :8000) and the Lane C agent (`email_agent:app`,
:8001) ([`../../backend/Dockerfile`](../../backend/Dockerfile)).

| Tech | Version | Where pinned |
|------|---------|--------------|
| Python | 3.12 in CI and the image; `requirements.txt` states 3.11+ | `.github/workflows/ci.yml`, `backend/Dockerfile` (`python:3.12-slim`) |
| FastAPI | 0.142.2 | `constraints.txt` |
| uvicorn | 0.54.0 | `constraints.txt` |
| Pydantic / pydantic-settings | 2.13.5 / 2.x | `constraints.txt` |
| SQLAlchemy (async) | 2.1.3 | `constraints.txt` |
| asyncpg | 0.31.0 | `constraints.txt` |
| pgvector (Python) | 0.5.0 | `constraints.txt` |
| httpx | 0.28.1 | `constraints.txt` (agent model calls, Presidio, Ollama) |
| google-genai | 2.28.0 | `constraints.txt` (embeddings and `/ask` only; the agent calls Gemini over HTTP in `gemini_client.py`) |
| scikit-learn | 1.9.1 | `constraints.txt` (priority classifier baseline) |
| Pint | 0.26.1 | `constraints.txt` (normalisation layer) |
| pypdf | 6.19.0 | `constraints.txt` |
| PyJWT | 2.15.1 | `constraints.txt` (Supabase access tokens) |
| pytest | 9.1.1 | `constraints.txt` |
| ruff | 0.16.10 | `constraints.txt`; the only linter, no formatter enforced |

Optional training dependencies (torch, transformers, datasets) live in
[`../../backend/requirements-ml.txt`](../../backend/requirements-ml.txt) and are not installed by CI
(`make ml-deps`).

## Listener (`listener/`)

| Tech | Version | Where pinned |
|------|---------|--------------|
| Go | 1.26.5 | [`../../listener/go.mod`](../../listener/go.mod); build image `golang:1.26.5-alpine`, runtime `distroless/static-debian12:nonroot` |
| cloud.google.com/go/pubsub | v1.51.1 | `go.mod` |
| google.golang.org/api (Gmail) | v0.299.0 | `go.mod` |
| golang.org/x/oauth2 | v0.37.0 | `go.mod` |

The listener writes to Supabase over PostgREST (`/rest/v1/...`, `listener/dedupe.go`).

The attachment reader (`listener/attachment-reader/`) is a Python service built on the pinned
`presidio-image-redactor` image (Tesseract and spaCy included), plus `pypdfium2==5.13.0`.

## Dashboard (`frontend/frontend/mail-clarity-dash-main/`)

| Tech | Version | Where pinned |
|------|---------|--------------|
| Node.js | 22 | `.github/workflows/ci.yml` |
| npm | 11.6.4 | `package.json` `packageManager` |
| React | ^19.3.0 | `package.json` |
| TanStack Start / Router | ^1.168.60 / ^1.170.41 | `package.json` |
| TanStack Query | ^5.104.0 | `package.json` |
| Vite | ^8.3.1 | `package.json`, configured through `@lovable.dev/vite-tanstack-config` |
| TypeScript | ~6.0.3 | `package.json` |
| Tailwind CSS | ^4.2.1 (`@tailwindcss/vite`) | `package.json` |
| Radix UI primitives | 1.x | `package.json` |
| i18next / react-i18next | ^26.4.2 / ^17.0.15 | `package.json` |
| Zod | ^4.5.2 | `package.json` |
| Recharts | ^3.10.1 | `package.json` |
| Vitest | ^5.0.3 | `package.json` |
| ESLint / Prettier | ^10.11.0 / ^3.9.9 | `package.json` |
| openapi-typescript | ^7.13.0 | `package.json` (types generated from the backend's OpenAPI schema) |

The same project also builds the Chrome side panel (`npm run build:extension`, `make extension`).

## Data

| Tech | Version | Notes |
|------|---------|-------|
| PostgreSQL | 16 | Hosted on Supabase; CI tests against the `pgvector/pgvector` pg16 image (digest-pinned in `ci.yml`) |
| pgvector | extension | `embedding` (1536 dims, Gemini) and `local_embedding` (768 dims, Private mode); see [`db-schema.md`](db-schema.md) |
| Supabase | hosted | Postgres, PostgREST (listener writes), Google sign-in and admin auth ([`../../docs/adr/0004-admin-console-supabase-auth.md`](../../docs/adr/0004-admin-console-supabase-auth.md), [`../../docs/adr/0005-dashboard-google-sign-in.md`](../../docs/adr/0005-dashboard-google-sign-in.md)) |

Migrations are plain SQL in `backend/app/db/migrations/`, applied by `scripts/migrate.py` (`make migrate`).

## Models and AI services

| Service | Used for | Configured by |
|---------|----------|---------------|
| Google Gemini | agent stages (default `gemini-3.5-flash-lite`, optional fallback), embeddings (`gemini-embedding-001`), `/ask` (`gemini-2.5-flash`) | `GEMINI_AGENT_MODEL`, `GEMINI_FALLBACK_MODEL`, `GEMINI_CHAT_MODEL`; constants in `backend/gemini_client.py` and `backend/app/core/constants.py` |
| Ollama (Private mode) | local drafting, embeddings and scan checks on the company's machine | `LOCAL_LLM_URL`, `LOCAL_LLM_MODEL`, `LOCAL_EMBEDDING_MODEL`, `LOCAL_VISION_MODEL`; no model is set by default ([`../features/local-model.md`](../features/local-model.md)) |
| Microsoft Presidio | NER masking in the listener; the backend's document masking and typed-name check; the agent's draft PII scan | analyzer :5001, anonymizer :5002, digest-pinned in [`docker-compose.yml`](../../docker-compose.yml) |

Orchestration is direct HTTP calls with `asyncio` fan-out; no LangChain or LangGraph
([`../../docs/adr/0002-orchestration-framework.md`](../../docs/adr/0002-orchestration-framework.md)).
Every model call goes through `backend/model_gateway.py`. The pipeline itself is described in
[`../agent-pipeline.md`](../agent-pipeline.md).

## Containers

[`../../docker-compose.yml`](../../docker-compose.yml) runs `presidio-analyzer`,
`presidio-anonymizer` and the attachment reader (:5003), bound to 127.0.0.1, read-only, with no
Linux capabilities and memory caps. The backend and listener each have a Dockerfile; Ollama is run
separately by whoever offers Private mode.

## Hosting

| Piece | Where | Defined in |
|-------|-------|------------|
| Dashboard | Vercel (Nitro's Vercel preset, detected at build); `/api/*` rewritten to the backend at the edge | `frontend/frontend/mail-clarity-dash-main/nitro.config.ts` |
| API, worker and agent | One Render web service (Starter) from the backend image, started by `start-render.sh` | `render.yaml`, `backend/start-render.sh`, `backend/app/combined.py` |
| Presidio for the backend | A private Render service (Standard, 2 GB), same pinned image | `render.yaml` |
| Listener | A laptop, with its own local Presidio; `make tunnel` is the free fallback for the backend | `docker-compose.yml` profile `tunnel`, `infra/tunnel/` |

Details and limits: [`../features/free-hosting.md`](../features/free-hosting.md).

## CI (`.github/workflows/`)

| Workflow | Jobs |
|----------|------|
| `ci.yml` (PRs and pushes to `main`) | `backend` (ruff, pytest, image build), `database` (migrations twice, then `test_database.py` on pgvector pg16), `api-types` (generated dashboard types match the backend schema), `frontend` (tsc, eslint, vitest, build, extension build, palette check), `listener` (build, vet, `go test` with Presidio required, gofmt), `attachment-reader` (tests inside its image) |
| `codeql.yml` | CodeQL for Python, JavaScript/TypeScript and Go; pull requests and pushes to `main`, and weekly |
| `release-please.yml` | release PRs and `CHANGELOG.md` |
| `supabase-keepalive.yml` | queries the database every two days so the hosted project stays active |

## Replaced or removed

- **n8n:** retired; archived under `legacy/n8n/` and `legacy/n8n-webhook/`. Nothing calls it.
- **Next.js:** never shipped; the abandoned scaffold is in `legacy/placeholders/`. The dashboard is Vite + TanStack Start.
- **Python listener:** replaced by the Go listener; the old stub is in `legacy/placeholders/listener/`.
- **Anthropic SDK, Claude models, black:** not used anywhere in the code.
- **Classifier / reasoner / drafter model tiers:** replaced by one model per provider for every stage.
