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
- `DashboardEmail` carries `isRead` (opened at least once; anything new is unread) and a
  `priority` that is the classifier's prediction **after** the per-user policy layer has been
  applied — see the Personalisation section of `db-schema.md`. Consumers should treat `priority`
  as "what this user should see", not as the raw model output.
- `DashboardEmail.sources` lists the policy passages the cached draft was grounded on, as
  `{ label, chunkId, excerpt, score }` (`score` is cosine similarity, 0..1), captured when the
  draft was generated. Empty for a draft generated before migration 0011, or with no policy
  retrieved. Additive: `label` keeps its meaning.
- `DashboardEmail.quantities` lists every quantity in the masked body (weight, length, volume,
  temperature, area, speed) as `{ text, system: "metric"|"imperial", metric: {value, unit},
  imperial: {value, unit} }`. The side matching `system` is the figure exactly as written; the
  other is a conversion to three significant figures (whole units from 100 up). Currency is never
  converted. See [`../features/normalisation-layer.md`](../features/normalisation-layer.md).
- `GET /system/info` returns non-secret runtime configuration (model names, feature flags,
  corpus counts) for the dashboard's Settings view. Never add keys, URLs or credentials to
  it — the browser reads it.
- Ingestion routes (`POST /documents`, `POST /documents/upload`) are rate limited to 20
  requests per 60s per client IP; over that returns `429` with `Retry-After`. Uploads are
  capped at 10 MB (`413`) and must carry a real `%PDF-` header (`400`).
- Model-spending routes (`POST /search`, `POST /ask`, `POST /emails/{id}/regenerate`,
  `POST /emails/{id}/refine`, `POST /emails/{id}/translate`) are rate limited to 10 requests per 60s per client IP; over that
  returns `429` with `Retry-After`.
- Every response carries `X-Request-ID` (a caller-supplied one is kept when it is 1-64 chars of
  `[A-Za-z0-9._-]`, otherwise replaced), and the backend forwards it to Lane C so both logs share
  it. Every response also carries `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` and a `default-src 'none'` CSP (the
  demo page at `/` gets a CSP that allows its inline script). Implementation:
  `backend/app/core/middleware.py`.
- Lane C's `/process-email` and `/refine` answer `503` (or `504` when the draft's deadline ran
  out) with `{"detail": "<gemini error code>"}` when Gemini fails. See
  [`../features/llm-resilience.md`](../features/llm-resilience.md).
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

### Dashboard (email view)

**`POST /emails/{id}/translate`** — the masked body in another language, for reading only.
- Request: `{ "language": "en" | "ms" | "zh" }` · Response 200: `{ "language": string, "text": string }`
- 404 unknown email · 422 `translation_unfaithful` when the result changed a redaction marker or
  dropped a figure (checked through the normalisation layer) · 503/504 when Gemini fails.
- Not stored. Rate limited with the other model-spending routes. Only the masked body is sent,
  as plain text (markup stripped). See [`../features/translation.md`](../features/translation.md).

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
