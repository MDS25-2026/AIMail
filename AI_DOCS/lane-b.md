# Lane B — ML & Retrieval (RAG)

Working notes + architecture for the retrieval lane. Doubles as meeting prep.

## 1. What this lane is

The retrieval brain. It turns company policy documents into a searchable "meaning index"
so the assistant can ground email replies in real policy instead of guessing. In RAG terms
this lane owns the "Retrieval" (finding the right policy); it hands passages to the
generation lane (Lane C), which writes the reply. Also covers a planned trained priority
classifier for inbox triage.

## 2. What's done

- Full retrieval pipeline, running live on Supabase (Postgres + pgvector) + Google Gemini
  embeddings. Proven end to end on the real Code of Conduct PDF.
- Write path (upload): PDF -> extract text -> split into overlapping chunks -> embed each to
  a 1536-dim vector -> store.
- Read path (search): question -> embed -> cosine search over stored vectors -> top-k
  passages with scores.
- Demo UI (backend page + Next.js frontend): scored search, knowledge-base panel with
  provenance, PDF upload + preview, and a one-line trace of the vector-search steps.
- Full RAG loop demo (/ask): retrieve chunks -> generate a grounded answer with citations
  via Gemini Flash. Note: real reply generation is Lane C; this is a scoped demo of the loop.
- Retrieval eval harness: precision@k, hit-rate, MRR.
- 17 automated tests passing; linted; frontend type-checked.
- Seam 2 (retrieval -> generation) contract defined.

## 3. Challenges / next steps

- Setup hurdles, now resolved: Supabase free-tier needs the IPv4 session pooler; a Windows
  hosts-file entry was sinkholing the Gemini API to 127.0.0.1.
- Team decision needed: priority-classifier dataset (public corpus vs hand-labelled).
- Confirm the retrieval -> generation handoff with the generation-lane owner.
- Build order: run eval for baseline numbers -> add query reformulation (beat baseline) ->
  trained priority classifier.

## Architecture (flow)

```
WRITE   PDF -> chunks -> [Gemini embed] -> vectors -> Postgres/pgvector
READ    question -> [Gemini embed] -> query vector -> cosine search -> top-k passages
```

## Key files

- `backend/app/rag/chunk.py` — PDF text extraction + word-window chunking
- `backend/app/rag/embed.py` — Gemini embeddings + L2 normalization
- `backend/app/rag/ingest.py` — write path (chunk/embed/store; replace-on-reupload)
- `backend/app/rag/retrieve.py` — read path (embed query, cosine top-k) — Seam 2 output
- `backend/app/rag/library.py` — knowledge-base inventory
- `backend/app/rag/eval.py` — retrieval metrics
- `backend/app/rag/generate.py` — grounded-answer generation for /ask (Lane C territory; demo)
- `backend/app/db/models.py` + `migrations/0001_rag_tables.sql` — `document` / `chunk` / `embedding`
- `backend/app/main.py` — REST API (`/search`, `/documents`, `/documents/upload`, `/ask`)
- `frontend/app/page.tsx` — dashboard UI

## Gotchas

- `gemini-embedding-001` does NOT auto-normalize at 1536 dims — must L2-normalize manually.
- Embedding dim is pinned at 1536 (pgvector HNSW indexes up to 2000 dims; native is 3072).
- Retrieval reads the vector store, never the PDF. Changing a policy = re-upload (same
  filename replaces; different filename adds alongside).
- Three tables are split so a model swap re-embeds without re-chunking.

## Common operations

```bash
cd backend
../.venv/bin/python scripts/apply_migration.py      # create tables (first run)
../.venv/bin/python scripts/ingest.py <pdf> "Title" # ingest a policy PDF
../.venv/bin/uvicorn app.main:app --reload          # backend at :8000
../.venv/bin/pytest                                 # tests
cd ../frontend && npm run dev                        # frontend at :3000
```
