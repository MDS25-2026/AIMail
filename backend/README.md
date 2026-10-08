# backend

The brain of AImail. FastAPI service for Lanes B + C: RAG retrieval, the priority classifier, and the multi-agent reply pipeline (generation on Gemini, `email_agent.py`). Reads masked email and writes/caches drafts in Postgres + pgvector, exposes REST endpoints for the dashboard, and sends approved replies via the Gmail API. PII masking happens in the listener, not here.

## Run locally

`app/main.py` serves the dashboard API (emails list/detail, draft regenerate/refine/send) plus the
RAG retrieval endpoints (`/search`, `/ask`, `/documents`).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -c constraints.txt   # the versions make check last passed with
pytest                                # offline logic tests (no DB / network)

# with DATABASE_URL + GOOGLE_API_KEY set in the repo-root .env:
make migrate                          # (from repo root) create all tables
make seed                             # load sample policy chunks
uvicorn app.main:app --reload         # dashboard API + retrieval on http://localhost:8000
```

## Run in a container

One image serves both the API and the agent (`Dockerfile`); configuration comes only from the
environment, and `.dockerignore` is an allowlist, so the study data and labelled email in this folder
never enter it.

```bash
docker build -t aimail-backend backend/
docker run --env-file .env -p 8000:8000 aimail-backend                                   # API
docker run --env-file .env -e APP=email_agent:app -e PORT=8001 aimail-backend            # agent
docker run --env-file .env aimail-backend python scripts/migrate.py                      # migrations
```

Probes: `GET /healthz` (process up) and `GET /readyz` (database reachable for the API, a model
configured for the agent). Logs are JSON in the image (`LOG_FORMAT=json`).

## Key dependencies

- Python 3.11+
- FastAPI
- SQLAlchemy + asyncpg (Postgres)
- pgvector
- Gemini via HTTP (google-genai for Lane B embeddings/reformulation; direct HTTP in the agent)
- Pydantic v2

## Env vars

Defined in the repo-root [`../.env.example`](../.env.example). Expected keys:

- `DATABASE_URL` — Supabase Postgres (Session pooler)
- `GOOGLE_API_KEY` — the one Google AI (Gemini) key: embeddings, query reformulation, and the agent
- `LOCAL_LLM_URL`, `LOCAL_LLM_MODEL` — Private mode's local model in Ollama (e.g. `gemma4:e2b`); empty model = not offered
- `LOCAL_EMBEDDING_MODEL` — Private mode's search model on the same Ollama (e.g. `embeddinggemma`); empty = Private mode drafts without search
- `GEMINI_CHAT_MODEL` — optional, defaults to `gemini-2.5-flash`
- `GOOGLE_API_KEY` — Gemini for the Lane C agent
- `FRONTEND_ORIGINS` — deployed dashboard origins for CORS, comma-separated (any localhost port is allowed in dev)
- `ENVIRONMENT` — `dev`, `staging` or `prod`; outside dev, missing secrets or localhost public URLs stop startup
- `AGENT_TOKEN` — shared secret between the backend and the agent
- `BACKEND_API_TOKEN` — bearer token required on every route except `GET /`. Empty means the API
  refuses all requests rather than silently running unauthenticated
- `EMAIL_AGENT_URL` — where the backend calls Lane C (default `http://localhost:8001`)
- `PRIORITY_MODEL` — `baseline` (TF-IDF) or `distilbert` (fine-tuned); selects which predictor
  `backfill_importance.py` uses
- `MAILBOX_OWNER_EMAIL` — keys the per-user policy layer; blank falls back to neutral defaults

## Folder structure

```
backend/
├── email_agent.py           # Lane C reply-generation agent (Gemini), served on :8001
├── app/
│   ├── main.py              # FastAPI entrypoint: dashboard API + retrieval
│   ├── dashboard.py         # assemble the email view, generation cache, regenerate/refine/send
│   ├── contracts.py         # cross-lane data shapes (single source of truth)
│   ├── personalisation.py   # per-user policy applied AFTER the classifier predicts (Lane B)
│   ├── audit.py             # best-effort audit trail for generate/refine/send
│   ├── gmail_send.py        # send approved replies via the Gmail API
│   ├── static/              # demo.html (retrieval showcase page)
│   ├── rag/                 # embeddings, ingestion, retrieval, eval (Lane B)
│   ├── ml/                  # priority classifier + temporal layer (Lane B)
│   ├── db/                  # SQLAlchemy models + migrations
│   └── core/                # config, constants, auth, rate limiting
├── scripts/                 # migrate, seed, ingest, eval, train, generate
├── tests/
└── requirements.txt
```
