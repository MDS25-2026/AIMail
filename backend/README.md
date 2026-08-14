# backend

The brain of AImail. FastAPI service for Lanes B + C: RAG retrieval, the priority classifier, and the multi-agent reply pipeline (generation on Gemini, `email_agent.py`). Reads masked email and writes/caches drafts in Postgres + pgvector, exposes REST endpoints for the dashboard, and sends approved replies via the Gmail API. PII masking happens in the listener, not here.

## Run locally

`app/main.py` serves the dashboard API (emails list/detail, draft regenerate/refine/send) plus the
RAG retrieval endpoints (`/search`, `/ask`, `/documents`).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                # offline logic tests (no DB / network)

# with DATABASE_URL + GEMINI_API_KEY set in the repo-root .env:
make migrate                          # (from repo root) create all tables
make seed                             # load sample policy chunks
uvicorn app.main:app --reload         # dashboard API + retrieval on http://localhost:8000
```

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
- `GEMINI_API_KEY` — Gemini embeddings (RAG) + query reformulation (Lane B)
- `GEMINI_CHAT_MODEL` — optional, defaults to `gemini-2.5-flash`
- `GOOGLE_API_KEY` — Gemini for the Lane C agent
- `FRONTEND_ORIGIN` — dev CORS origin for the dashboard (default `http://localhost:3000`)

## Folder structure

```
backend/
├── email_agent.py           # Lane C reply-generation agent (Gemini), served on :8001
├── app/
│   ├── main.py              # FastAPI entrypoint: dashboard API + retrieval
│   ├── dashboard.py         # assemble the email view, generation cache, regenerate/refine/send
│   ├── contracts.py         # cross-lane data shapes (single source of truth)
│   ├── gmail_send.py        # send approved replies via the Gmail API
│   ├── static/              # demo.html (retrieval showcase page)
│   ├── rag/                 # embeddings, ingestion, retrieval, eval (Lane B)
│   ├── ml/                  # priority classifier + temporal layer (Lane B)
│   ├── db/                  # SQLAlchemy models + migrations
│   └── core/                # config, constants
├── scripts/                 # migrate, seed, ingest, eval, train, generate
├── tests/
└── requirements.txt
```
