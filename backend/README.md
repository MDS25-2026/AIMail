# backend

The brain of AImail. FastAPI service that handles PII masking, Claude API calls, the multi-agent reply pipeline, and Postgres + pgvector reads/writes. Exposes REST endpoints for the frontend and accepts forwarded webhook payloads from the listener.

## Run locally

_Not built yet._ Placeholder steps:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # TODO
uvicorn app.main:app --reload     # TODO
```

## Key dependencies

- Python 3.11+
- FastAPI
- SQLAlchemy + asyncpg (Postgres)
- pgvector
- Anthropic SDK (Claude API)
- Pydantic v2

## Env vars

Defined in `.env.example` (TODO). Expected keys:

- `ANTHROPIC_API_KEY`
- `DATABASE_URL`
- `LISTENER_SHARED_SECRET`
- `LOG_LEVEL`

## Folder structure

```
backend/
├── app/
│   ├── main.py              # FastAPI entrypoint (TODO)
│   ├── api/                 # REST routes
│   ├── agents/              # multi-agent pipeline
│   ├── pii/                 # masking + un-masking
│   ├── claude/              # Claude API client wrapper
│   ├── db/                  # SQLAlchemy models, migrations
│   └── core/                # config, logging, deps
├── tests/
└── requirements.txt
```
