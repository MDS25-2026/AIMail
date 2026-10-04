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
- `DashboardEmail.threadContext` lists the other masked messages in the same Gmail thread,
  oldest first, as `{ sender, snippet }` (detail and regenerate responses; the list endpoint
  leaves it empty). The draft now sees up to five earlier messages, labelled by position and never
  by sender address.
- `DashboardEmail.masking` is `"complete"`, `"pending"` (quarantined because NER masking was
  unavailable, #109) or `"abandoned"` (the listener gave up: deleted from Gmail, or never
  maskable). For the last two, subject, body and preview are empty and no draft exists;
  `/translate` answers 409 `masking_pending`.
- `DashboardEmail.quantities` lists every quantity in the masked body (weight, length, volume,
  temperature, area, speed) as `{ text, system: "metric"|"imperial", metric: {value, unit},
  imperial: {value, unit} }`. The side matching `system` is the figure exactly as written; the
  other is a conversion to three significant figures (whole units from 100 up). Currency is never
  converted. See [`../features/normalisation-layer.md`](../features/normalisation-layer.md).
- `GET /system/info` returns non-secret runtime configuration (model names, feature flags,
  corpus counts) for the dashboard's Settings view. Never add keys, URLs or credentials to
  it — the browser reads it.
- Ingestion routes mask the text before anything is stored (2026-10-04): fixed formats, then
  Presidio for names, emails, phones, cards and IBANs. If Presidio is unreachable they answer `503`
  `masking_unavailable` and store nothing.
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
- `POST /emails/{id}/send` checks the draft on the server (2026-10-04): `422` for an empty draft
  or one over 20,000 characters (validation), `422` `redaction_markers` when the draft still holds
  `[Redacted]` or a `[*_REDACTED]` token, and `409` `masking_pending` for a quarantined email.
  `504` `send_outcome_unknown` means Gmail may have sent the reply but its answer was lost; the email
  stays marked sent so it is never sent twice, and the reader should check Gmail's Sent folder.
  `502` `send_failed` still means Gmail never accepted it, and it can be approved again.
- `POST /emails/{id}/regenerate` and `POST /emails/{id}/refine` no longer answer `200` with the
  old draft when nothing changed (2026-09-30). They answer `502` `agent_unavailable` (the agent
  or retrieval failed; retry later), `422` `draft_refused` (regenerate only: the model failed on
  this content and the reviewed draft is kept), `409` `masking_pending` (quarantined) or `409`
  `already_sent`, each as `{"detail": "<code>"}`. A regenerate the router judges needs no reply
  is still `200`, with an empty draft.
- Lane C's `/refine` (2026-10-04) takes `thread_context`, `rag_context` and `action_items` besides
  `email_body`, `draft` and `instruction`, and runs the same critic and gates as `/process-email`.
  It answers `{draft, confidence, issues, needs_human_review, grounding_ok, pii_clean, tone_match,
  completeness, pii_findings, unsupported_specifics, unaddressed_requests, review_reasons,
  model_calls}`, and the backend stores that verdict with the refined draft. The backend masks
  emails, ICs, passports, card and phone numbers in the typed draft and instruction first (names
  stay), and does the same for `/search` and `/ask` queries (`app/core/typed_text.py`). A refine
  the model refuses answers `422` `draft_refused` through the backend.
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

### Admin console (`/admin`, ADR 0004)

A separate app mounted at `/admin`. The shared bearer token does **not** apply and does not grant
access: every call below except sign-in needs the `aimail_admin` HttpOnly cookie for a Supabase
user with `app_metadata.role = "admin"`. State-changing calls must send `X-AIMail-Admin: 1`. The
dashboard calls these with `credentials: "include"`. Errors are `{"detail": "<code>"}`.

- **`POST /admin/session`** `{ email, password }` → 200 `{ email }` and sets the session cookies ·
  401 `invalid_credentials` · 403 `not_an_admin` · 429 after 5 tries in 5 minutes ·
  503 `admin_auth_not_configured` / `supabase_unavailable`.
- **`POST /admin/session/refresh`** → 200 `{ email }`, renews the cookies from the refresh cookie.
- **`DELETE /admin/session`** → 204, revokes the Supabase session and clears both cookies.
- **`GET /admin/session`** → `{ email }` of the signed-in admin; 401 `admin_signed_out` /
  `admin_session_invalid`.
- **`GET /admin/overview?days=1..90`** → mailbox counts, privacy counts, review-reason categories,
  model health (attempts, outcomes, fallback use, p50/p95 model time per draft).
- **`GET /admin/flagged?limit=`** → drafts awaiting review: id, masked subject, reason categories.
- **`GET /admin/audit?limit=&failures_only=`** → recent `audit_log` rows, detail cut to 240 chars.

No admin response contains an email body, a draft, or the text after a review reason's colon.

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
