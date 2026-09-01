# API contracts

This file is the **contract between frontend and backend**. Every REST endpoint AImail exposes is documented here. Frontend and backend must both match this file.

## Rules

- Add an endpoint here **before** writing it.
- Update this file in the same PR that changes a request/response shape.
- Keep examples short — link to the relevant feature spec for full detail.

## Conventions

- Base URL: `${NEXT_PUBLIC_BACKEND_URL}` (configurable per environment).
- All requests/responses are JSON.
- Auth: **shared bearer token, required on every endpoint except `GET /`.** Send
  `Authorization: Bearer <BACKEND_API_TOKEN>`; the value lives in the repo-root `.env`
  (frontend reads the same value as `VITE_BACKEND_API_TOKEN`). Missing or wrong token returns
  `401`; if the server has no token configured it returns `503` and serves nothing — auth is
  never silently disabled. Implementation: `backend/app/core/auth.py`. Per-user Supabase JWTs
  are the planned upgrade and replace only that file; AImail serves one shared mailbox, so
  per-user identity is deferred, not forgotten.
- The Lane C agent (`:8001`) carries no token of its own and is bound to `127.0.0.1`; it is
  reachable only by the backend on the same host.
- Errors follow this shape:

```json
{
  "error": {
    "code": "PII_MASKING_FAILED",
    "message": "Human-readable summary",
    "details": {}
  }
}
```

## Endpoints

### Lane B — retrieval demo (provisional)

These back the retrieval demo (`backend/app/main.py`). **Provisional** — a demo surface, not the
finalised contract; production shapes, auth, and the error envelope below get pinned with Lane D.
See [`../features/rag-retrieval.md`](../features/rag-retrieval.md).

**`POST /search`** — semantic policy search.
- Request: `{ "query": string, "k"?: int (1–20, default 5) }`
- Response 200: `[{ "chunk_id": uuid, "content": string, "similarity_score": float, "source_title": string }]`

**`POST /ask`** — full RAG loop: retrieve + generate a grounded answer (a demo of Lane C's job).
- Request: `{ "question": string, "k"?: int }`
- Response 200: `{ "answer": string, "sources": [ContextChunk] }`

**`GET /documents`** — knowledge-base inventory.
- Response 200: `[{ "document_id": uuid, "title": string, "source": string, "doc_type": string, "chunk_count": int }]`

**`POST /documents`** — add a policy by pasting text.
- Request: `{ "title": string, "text": string }` · Response 200: `{ "chunks": int }`

**`POST /documents/upload`** — add a policy by uploading a PDF (multipart).
- Request: `multipart/form-data` with `file` (PDF) · Response 200: `{ "chunks": int }` · 400 if not a readable PDF.

> Drift note: these currently return FastAPI defaults (`{"detail": ...}` on error, bare JSON bodies),
> not the `{ "error": {...} }` envelope above. Aligning them is a follow-up when the contract is finalised.

### Shared data shapes (the Seams)

Cross-lane shapes live in `backend/app/contracts.py` — the **single source of truth** both lanes
import (never hand-copy). Provisional; adding a field is safe, changing/removing one is a break.

- **`ContextChunk`** — Lane B retrieval -> Lane C (in-process): `{ chunk_id, content, similarity_score, source_title }`.
- **`EmailPriority`** — Lane B classifier -> Lane D dashboard (per email): `{ importance: LOW|MEDIUM|HIGH, confidence, deadline_at, priority_score, model_version }`.

### TODO

- [ ] `POST /webhooks/email` — listener → backend ingress.
- [ ] `GET /threads` — list threads with most recent draft.
- [ ] `GET /threads/{id}` — full thread + draft.
- [ ] `POST /drafts/{id}/approve` — approve draft, trigger send.
- [ ] `POST /drafts/{id}/edit` — user edits before approval.
- [ ] `POST /drafts/{id}/reject` — discard draft.
