# API contracts

This file is the **contract between frontend and backend**. Every REST endpoint AImail exposes is documented here. Frontend and backend must both match this file.

> **Errors (2026-10-08):** every error is `{"error": {"code": "<code>", "message": "<English, for logs>"}}`.
> Codes and their statuses live in one registry, `backend/app/core/errors.py` (`ErrorCode`); the older
> `{"detail": "<code>"}` responses are gone. Some codes were renamed in the move: `DATABASE_UNREACHABLE` ->
> `database_unreachable`, `AI_SERVICE_UNREACHABLE` -> `ai_service_unreachable`, `email_too_long_to_translate` ->
> `too_large`, `agent_unreachable` -> `agent_unavailable`, and PDF upload errors -> `not_pdf` / `unreadable_pdf`.

## Rules

- Add an endpoint here **before** writing it.
- Update this file in the same PR that changes a request/response shape.
- Keep examples short — link to the relevant feature spec for full detail.

## Conventions

- Base URL: `${VITE_BACKEND_URL}` (configurable per environment).
- All requests/responses are JSON.
- Auth (ADR 0005, 2026-10-04): **every endpoint except `GET /` and the `/auth` sign-in routes needs
  one of** the dashboard's `aimail_session` cookie (set by Google sign-in), a Supabase access token
  as `Authorization: Bearer`, or the server-side `BACKEND_API_TOKEN` as a bearer (scripts and tests
  only; never in the browser). No credential returns `401` `signed_out`, a bad one `401`
  `session_invalid`, and a cookie request that changes state without `X-AIMail-Client: 1` returns
  `403` `client_header_missing`. An unset `BACKEND_API_TOKEN` never matches. Implementation:
  `backend/app/core/auth.py`.
- Mailbox scope: a signed-in user sees mail only once their own Gmail is connected. Anyone else gets an empty page from `GET /emails` and `[]` from `GET /documents`, and `404` from every
  route about one email, `/search`, `/ask` and document ingestion.
- **Holding reply (2026-10-06, `specs/features/holding-reply.md`):** `GET /settings/holding-reply`
  returns `{enabled, activeWhen, workDays, workStart, workEnd, timezone, leaveFrom, leaveUntil,
  audience, scope, cooldownDays, templates: {en?, ms?, zh?}, defaultLanguage}` (defaults with
  `enabled: false` when unset); `PUT` validates and saves it (`422` with a code for an unknown
  placeholder, `{return_date}` without leave dates, an empty template, or an unknown timezone).
  `GET /holding-replies?limit=` lists `{id, emailId, recipient, language, scheduledFor, sentAt,
  cancelledReason}` newest first; `DELETE /holding-replies/{id}` cancels one still waiting (`409`
  once sent). All per signed-in user; `403 account_only` for the script token.
- **Sender verification and audit (2026-10-07, `specs/features/sender-verification-and-audit.md`):**
  every email carries `authStatus`: `pass`, `spoof_detected` or `sender_confirmed`. For a
  `spoof_detected` email, regenerate and refine answer `409 sender_unverified`, and so does send.
  `POST /emails/{id}/confirm-sender` returns the email, now `sender_confirmed` (404 if not the
  caller's). `GET /audit?limit=` (1-100, default 50) returns `{is_chain_intact, total_records,
  verified_records, head_hash, events: [{id, created_at, action, detail, success, prev_hash,
  current_hash, user_id, is_verified}]}`. Since 2026-10-21 (`specs/features/admin-only-pages.md`)
  it is for admins and the script token only (404 `not_found` for anyone else) and shows everyone's
  rows; it takes `group` (`sending` | `drafting` | `privacy` | `mailbox` | `settings` | `admin` |
  `other`), `person` (a user id), `failures_only` and `window` (`day` | `week` | `month` | `all`), and
  adds `failedRecords`, `people: [{id, email}]`, and on each event `group` and `userEmail`.
  `GET /auth/session` adds `isAdmin`, and the admin console (`/admin/*`) also accepts the dashboard's
  session cookie when its token carries the admin role.
- **Reading a document (#195):** `GET /documents/{id}` returns `{document_id, title, source, doc_type,
  chunk_count, content, chunks: [...]}` for a document in the caller's library (`404` otherwise, or
  with no mailbox connected); rate limited like `GET /documents`.
- **Removing a document (2026-10-07, `specs/features/rag-retrieval.md`):** `DELETE /documents/{id}`
  returns `204` and removes the document, its chunks and both kinds of vector; `404` when it is not
  in the caller's library (someone else's, a past reply, or unknown); `422` for a malformed id.
- <a id="writing-style"></a>**Writing style (2026-10-06, `specs/features/writing-profile.md`):**
  `GET /profile/writing` returns `{description, learning, examples: [{id, text, source, createdAt}],
  habits: [{id, kind, value, evidence, outOf}], maxExamples}`; every text is the masked copy that
  was stored. `PUT /profile/writing/description` `{description}` and `POST /profile/writing/examples`
  `{text}` or `{emailId}` mask before storing and return the stored copy (`503 masking_unavailable`,
  nothing stored; `409 too_many_examples`; `404` for an email that is not the user's or not sent;
  `422 empty`/`too_long`). `PUT /profile/writing/learning` `{enabled}`.
  `DELETE /profile/writing/examples/{id}`, `DELETE /profile/writing/habits/{id}` (hidden for good)
  and `DELETE /profile/writing` (everything, including stored past replies; learning off) return `204`.
  While learning is on, a send also stores a past reply that drafts may cite as `rag_sources` with
  `label: "Your earlier reply"`; `GET /documents` never lists them. Per signed-in user;
  `403 account_only` for the script token. The agent's `/process-email` and `/refine` take
  `style_hint: str = ""` and `style_examples: list[str] = []`, fenced as data.
- **Expired Google access (2026-10-06, `specs/features/per-user-mailboxes.md`):** `GET /auth/session`
  also returns `needsReconnect` (bool). A send whose Google token was refused returns
  `409 google_access_expired`.
- **Private mode (2026-10-06, `specs/features/local-model.md`):** `GET /settings/private-mode`
  returns `{available, enabled, isDecided, model, search}` (`search`: `LOCAL_EMBEDDING_MODEL` is set, so
  private drafts search documents and past replies; `isDecided`: the user has switched it either way or
  answered the inbox offer, 2026-10-11); `PUT` `{enabled}` saves it (`409 private_mode_unavailable`
  when the company has not set `LOCAL_LLM_MODEL`). `POST /settings/private-mode/not-now` (`204`) is
  the inbox offer's "Not now": it stays off and the offer is not shown again. The agent's `/process-email`, `/refine` and
  `/translate` take `provider: "gemini" | "local"` (default `gemini`); a local call that cannot
  reach Ollama returns the same `503` as an unreachable Gemini.
- **Scanned attachments (2026-10-10, `specs/features/signature-detection.md`):**
  `GET /settings/scan-reading` returns `{available, mode}` (`mode`: `local` | `checked`;
  `available`: the company set `LOCAL_VISION_MODEL`); `PUT` `{mode}` saves it (`409
  scan_check_unavailable` for `checked` where it is not set up; `local` is always accepted).
- **Quiet hours, send later, snooze (2026-10-11, `specs/features/quiet-hours-send-later.md`):**
  `POST /emails/{id}/schedule` `{draft, sendAt}` holds the draft (checked as a send would be) and
  returns the email with `scheduledFor`; `DELETE` cancels it. `POST /emails/{id}/snooze` `{until}`
  hides it from `GET /emails` until then and marks it unread; `DELETE` brings it back. Both refuse a
  time in the past or over 60 days ahead (`422 time_out_of_range`). `GET/PUT/DELETE
  /settings/quiet-hours` (personal; DELETE follows the company default) returns `{company,
  personal, effective}`; `GET/PUT /admin/quiet-hours` edits the company default. The email gains
  `senderUtcOffsetMinutes`, `scheduledFor`, `scheduleCancelled` (`they_replied` | `you_replied` |
  `too_late` | `refused`), `snoozedUntil`. A send time past the email's vault retention is refused
  (`422 time_out_of_range`); snooze does not hide an email with a waiting send.
- **Write in my language (2026-10-13, `specs/features/write-in-my-language.md`):**
  `POST /emails/{id}/translate-draft` `{text}` returns `{language, text}`, the reader's reply in the
  email's language in placeholder form; nothing is stored.
- **Inbox threads (2026-10-13, `specs/features/inbox-threads.md`):** each `GET /emails` page holds whole
  threads, placed by their newest visible email; `limit` counts threads; the cursor is the last thread's
  newest email. The email gains `isAnswered` (list rows).
- **Readable emails (2026-10-12, `specs/features/readable-emails.md`):** the email gains
  `hasUnreadAttachment`; `threadContext` also lists the owner's replies sent from Gmail itself.
- **To-do redesign and status (2026-10-12, `specs/features/todo-redesign-and-status.md`):** `GET /todo`
  gains `doneToday` and leaves out snoozed emails. `DELETE /todo/waiting/{id}/dismiss` (204) undoes
  *Not waiting*. `GET /service-status` (public, cached 15 s, always 200) returns `{checkedAt, parts:
  {backend, database, masking, drafting, listener}}`, each `ok` | `degraded` | `down`. `/healthz` and
  `/readyz` are unchanged.
- **Drafting skips (2026-10-12, `specs/features/drafting-skips.md`):** the email gains `isAutomated`;
  `senderUtcOffsetMinutes` is null for automated mail and for a `+0000` offset. A model call for a Private
  mode owner on a server with no private model answers `409 private_model_unavailable`; an automated
  email is refused an automatic draft with `automated_email` (Regenerate still drafts it). A cancelled
  holding reply can carry `unfilled_field`.
- **To-do (2026-10-11, `specs/features/todo-page.md`):** `GET /todo` returns `{needsAction,
  needsReview, unsentDrafts: {emails, total}, waiting: [{id, subject, sentAt, threadId, workingDays,
  email, canFollowUp}], waitingDays, count}` (each list the newest 50; an email is in one list only).
  `POST /emails/{id}/dismiss` (No reply needed) and `DELETE` to undo; `POST /todo/waiting/{id}/dismiss`
  (Not waiting); `PUT /settings/todo` `{waitingDays}`. `POST /emails/{id}/send` takes `remindIfNoReply`
  (default false). Follow-ups (`canFollowUp`: the reply was sent through AIMail): `POST
  /todo/waiting/{id}/follow-up` returns `{draft, details}` (the draft in placeholder form, not stored,
  with the details of the thread it is numbered in); `POST /todo/waiting/{id}/follow-up/send`
  `{draft}` (`204`) sends it in the email's thread with the same checks and errors as
  `/emails/{id}/send`, plus `409 follow_up_unavailable` for a reply sent from Gmail, `409
  follow_up_stale` when they replied, a newer reply went or it was set aside since, and `409
  already_sent` once its follow-up has gone.
- **Saved reply templates (2026-10-11, `specs/features/reply-templates.md`):** signed-in users only.
  `GET /templates` (most recently used first); `POST /templates` and `PUT /templates/{id}` take
  `{title, body, language: en|ms|zh, triggerKeywords: string[]}` and return it with `id` and
  `lastUsedAt` (`409 too_many_templates` past 50; `422` past the length limits); `DELETE
  /templates/{id}` (204). `POST /templates/{id}/fill` `{emailId}` returns `{text}`: the template
  filled for that email (`{{name}}` as the sender's placeholder, `{{my name}}` the owner's, `{{today}}`
  the date), nothing stored. `POST /templates/{id}/adapt` `{emailId, tone}` returns the email with
  the agent's rewrite stored, as a refine does. `POST /templates/{id}/translate` `{language}`
  returns an unsaved copy (`422 translation_unfaithful` if a `{{variable}}` was lost). Someone
  else's template answers 404. The email detail gains `suggestedTemplateId`. A send whose draft
  still holds a `{{...}}` is refused with `422 unresolved_placeholders`.
- **Account (2026-10-05, `specs/features/per-user-mailboxes.md` "Disconnect and delete account"):**
  `DELETE /account/gmail` revokes the Google token, deletes the user's stored emails and their
  connection (`204`; `404 not_connected`). `DELETE /account` also deletes their documents, profile
  and Supabase sign-in, and clears the session cookies (`204`; `502 account_not_fully_deleted`, safe
  to repeat). Both need a signed-in user (`403 account_only` for the script token) and, with a
  cookie, `X-AIMail-Client: 1`.
- **Restorable masking (2026-10-05, `specs/features/restorable-masking.md`):** stored text carries
  numbered placeholders (`[PERSON_1]`, `[PHONE_2]`, kinds PERSON, EMAIL, PHONE, IC, PASSPORT,
  ACCOUNT, CARD, LOCATION, ORG), numbered once per thread. Detail, regenerate, refine and send
  responses add `details: [{placeholder, value, kind}]`, the owner's real values for display (on the
  list endpoint, each row carries its own email's details in that email's numbering; empty for older
  emails and once a vault expires). A draft sent with real details
  typed in is accepted; the backend stores it with placeholders. `POST /emails/{id}/send` adds
  `422 unresolved_placeholders` (a placeholder no vault can fill). Lane C: `/process-email` and
  `/refine` accept `sign_off` (the owner's name as a placeholder, never the name); payloads still
  never carry a real detail.
- `GET /emails/by-thread/{thread_id}` (2026-10-05, the Chrome extension): the newest of the
  signed-in user's messages in that Gmail thread, as `GET /emails/{id}` returns it (asking for the
  draft if needed). `thread_id` must be 8 to 24 lowercase hex characters (`422` otherwise); `404`
  when the user has no message in that thread. Same scope rules as every email route.
- `GET /emails?cursor=&limit=` (2026-10-08) answers one page, newest first:
  `{ "emails": [DashboardEmail], "nextCursor": string | null }`. `limit` is 1 to 100 (default 50;
  `422` outside). `nextCursor` goes back as `cursor` for the next, older page and is `null` on the
  last; it is opaque, and one this API did not issue is `422 invalid_request`. Paging is by
  `(created_at, id)`, so no email is skipped or shown twice when new ones arrive. Before this the
  list was the newest 50 and older mail could not be reached.
- **Mark unread (2026-10-11, `specs/features/plain-wording-and-polish.md`):** `POST
  /emails/{id}/unread` (`204`, `404` when not the caller's) clears `read_at`. `GET /emails/{id}`
  marks the email read unless `?markRead=false`, which the dashboard sends while the reader keeps
  an email they just marked unread open.
- **Review reasons as codes (2026-10-11):** the agent's `/process-email` and `/refine` add
  `review_codes: [{code, items}]` beside `review_reasons` (codes in `agent_contract.ReviewCode`;
  `pii_found` items are entity types only). The email adds `reviewReasons: [{code, items}]`, read
  from older drafts' text when they have no codes; an unrecognised one is `unknown`.
- `GET /emails/{id}` (2026-10-08) never writes the draft inside the request. An email with no draft
  yet that may be drafted answers at once with `isDrafting: true` and is queued
  (`messages.draft_requested_at`, migration 0032); the worker's "requested drafts" job, on every
  3 s whatever `AUTO_GENERATE` says, writes it. The dashboard fetches the email again every 3 s while
  `isDrafting` is true, for up to two minutes. Only the first attempt is queued this way; after a
  failure `isDrafting` is false and Regenerate (or the regular pass) takes over.
- **Per-user scope (per-user mailboxes, step 3):** every email and document route answers only for
  the signed-in user's own rows (`app/core/ownership.py`). Another user's email id answers `404`,
  exactly like an unknown id; `GET /emails` returns an empty page and `GET /documents` `[]` for a user with no
  connected Gmail; `/search`, `/ask` and drafting ground only on the user's own documents;
  `GET /auth/session`'s `hasMailbox` is true when the user has connected Gmail. The shared script
  token still sees everything, but `POST /documents` and `POST /documents/upload` with it answer
  `403 account_only`: a document needs an owner (`make ingest OWNER=<email>` instead; 2026-10-12).
- Sign-in: `GET /auth/google/start` redirects to Supabase, asking Google for `gmail.readonly` and
  `gmail.send` offline with consent (per-user mailboxes, step 2); the callback stores the user's
  sealed Gmail connection if Gmail read access was granted, and never fails sign-in over it.
  `GET /auth/callback` sets the session
  and redirects to the dashboard (or to `/signin?error=sign_in_failed|sign_in_unavailable`);
  `GET /auth/session` answers `{email, hasMailbox}`; `POST /auth/session/refresh` and
  `DELETE /auth/session` need `X-AIMail-Client: 1`.
- `DashboardEmail` carries `isRead` (opened at least once; anything new is unread) and a
  `priority` (`"critical"`, `"high"`, `"medium"`, `"low"`) that is the classifier's prediction **after**
  the per-user policy layer and deterministic SLA floor (migration 0034) have been applied — see the
  Personalisation section of `db-schema.md`. Consumers should treat `priority` as "what this user should see",
  not as the raw model output.
- `DashboardEmail.category` carries the 6-category B2B taxonomy prediction (`"client"`, `"vendor"`,
  `"internal"`, `"security"`, `"admin"`, `"personal"`), and `categoryConfidence` is the 0..1 calibrated
  confidence (Issue #141, migration 0033). Used by the dashboard for category badges and inbox filtering.
- `DashboardEmail.sources` lists the policy passages the cached draft was grounded on, as
  `{ label, chunkId, excerpt, score }` (`score` is cosine similarity, 0..1), captured when the
  draft was generated. Empty for a draft generated before migration 0011, or with no policy
  retrieved. Additive: `label` keeps its meaning.
- `DashboardEmail.threadContext` lists the other masked messages in the same Gmail thread,
  oldest first, as `{ sender, snippet }` (detail and regenerate responses; the list endpoint
  leaves it empty). The draft now sees up to five earlier messages, labelled by position and never
  by sender address. Since 2026-10-05 each entry also has `isOwnReply`: a reply the owner sent from
  AIMail appears right under the email it answered (`sender` empty, the dashboard shows "You"), and
  the draft sees it as "Your reply to earlier message N", masked like typed text. The listener no
  longer stores the mailbox's own sent copy (SENT without INBOX) as a new email. Since the
  conversation view (`specs/features/conversation-view.md`), each entry also carries `body` (the
  full masked body, placeholders renumbered for the thread) and `timestamp` (received, or for the
  owner's reply, sent), and `DashboardEmail.threadId` lets the inbox show one row per thread.
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
  requests per 60s per user (or client IP if unauthenticated); over that returns `429` with `Retry-After`. Uploads are
  capped at 10 MB (`413`) and must carry a real `%PDF-` header (`400`).
- Model-spending routes (`POST /search`, `POST /ask`, `POST /emails/{id}/regenerate`,
  `POST /emails/{id}/refine`, `POST /emails/{id}/translate`) are rate limited to 10 requests per 60s per user (or client IP if unauthenticated); over that
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
  Per-user mailboxes (2026-10-05): the reply goes out from the Gmail account the email arrived in,
  with that user's own token; `403` `send_not_granted` means the owner let AIMail read their Gmail
  but not send, and nothing was claimed (signing in again and ticking "send" fixes it).
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
  review_codes, model_calls, egress, prompt_version}`, and the backend stores that verdict with the refined draft. The backend masks
  emails, ICs, passports, card and phone numbers in the typed draft and instruction first (names
  stay), and does the same for `/search` and `/ask` queries (`app/core/typed_text.py`). A refine
  the model refuses answers `422` `draft_refused` through the backend.
- Lane C's `/process-email` and `/refine` answer `503` (or `504` when the draft's deadline ran
  out) with `{"detail": "<gemini error code>"}` when Gemini fails before a draft exists. Once one
  exists (2026-10-08), a failed critique or repair answers `200` with that draft, flagged for review
  with `critic unavailable: <code>` or `repair stopped: <code>`. See
  [`../features/llm-resilience.md`](../features/llm-resilience.md).
- Probes (2026-10-08, `app/core/health.py`): the backend and the agent answer `GET /healthz`
  (`200 {"status": "ok"}` while the process serves) and `GET /readyz` (`200` once ready, else `503`
  with `{"status": "failed", "checks": {"<name>": "failed"}}`; the backend checks its database and
  Presidio (since 2026-10-12), the agent that a model is configured, without calling one). Neither needs a session or the agent token,
  and neither is in the OpenAPI schema. The listener's own probes are on `:8095`.
- The Lane C agent (`:8001`) requires an `Authorization: Bearer <AGENT_TOKEN>` header (configured via `AGENT_TOKEN`) and is bound to `127.0.0.1`; it is
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

> Errors from these use the `{ "error": {...} }` envelope like every other route (one registry,
> `app/core/errors.py`, since 2026-10-08); success bodies are the bare JSON shown.

### Inbox search & Q&A assistant (2026-10-09, `specs/features/inbox-search-qa.md`, Issue #144)

**`POST /api/search/inbox`** — natural language conversational search across masked emails and knowledge base documents with grounded Gemini answer synthesis.
- Request:
  ```json
  {
    "query": string,
    "history"?: [{ "role": "user" | "assistant", "content": string (≤ 8000) }] (≤ 20 turns),
    "k_emails"?: int (1–20, default 5),
    "k_docs"?: int (1–10, default 3),
    "restore"?: boolean (default true; false while the reader hides details: placeholders stay in the
      answer and sources, sender addresses are left out, and `sender_vault` is empty)
  }
  ```
- Response 200:
  ```json
  {
    "answer": string,
    "sources": [
      {
        "source_type": "email" | "document",
        "id": string (uuid),
        "title": string,
        "subtitle": string,
        "snippet": string,
        "received_at": string | null
      }
    ],
    "sender_vault": { [placeholder: string]: string },
    "has_restored_pii": boolean,
    "intent": string | null
  }
  ```
- Only the user's last three questions from `history` reach the model; the assistant's turns never
  do, since their details were filled back in after the model answered (2026-10-11). Subjects and
  snippets use the same placeholder numbering as the bodies, so restored names match.
- Auth required (cookie or bearer). Scoped to the caller's mailbox and uploaded documents; with the
  bearer token (every user's scope) on Gemini, Private mode users' emails are left out.
- 401 `signed_out` / `session_invalid` · 404 `not_found` (no mailbox connected) · 422 `invalid_request` · 429 `rate_limited` · 503 `ai_service_unreachable`.

### Dashboard (email view)

**`POST /emails/{id}/translate`** — the masked body in another language, for reading only.
- Request: `{ "language": "en" | "ms" | "zh" }` · Response 200: `{ "language": string, "text": string }`
- 404 unknown email · 422 `translation_unfaithful` when the result changed a redaction marker or
  dropped a figure (checked through the normalisation layer) · 503/504 when Gemini fails.
- Not stored. Rate limited with the other model-spending routes. Only the masked body is sent,
  as plain text (markup stripped). See [`../features/translation.md`](../features/translation.md).

### Live inbox (2026-10-19, `specs/features/live-inbox.md`)

**`GET /events`** — server-sent events for the caller's own mailbox; a hint to refetch, never data.
- Cookie session only (the service token gets 404: no mailbox). Same `/api` rewrite as every call.
- Response 200 `text/event-stream`, `Cache-Control: no-store`, `CDN-Cache-Control: no-store`:
  `retry: 3000`, then `event: mailbox` with `data: {"kind": "new" | "draft" | "state" | "resync",
  "messageId": string | null}` and an `id:` sequence, and a `: ping` comment every 25 s while quiet.
- `new`: an email was stored; `draft`: its draft changed; `state`: read, sent, snoozed, dismissed,
  category, language, sender check or masking changed; `resync`: the backend's listener reopened,
  refetch everything. Ids only, never content.
- 429 `rate_limited` past three open streams per user. Not in the generated dashboard types (the
  body is a stream); the dashboard's `useMailboxEvents` is the only client.

### Compose (2026-10-21, `specs/features/compose.md`, epic #138)

New emails the signed-in user writes; the shared bearer token gets 403 `account_only`. Another user's
draft id answers 404 on every route. Text fields come back in placeholder form with `details` to fill
them in, as an email's draft does; the client sends the filled-in text and the backend turns known
details back into placeholders and numbers any new typed email, phone, IC, passport or card number.

`ComposeDraftView`: `{ id, to: string[], cc: string[], subject, brief, body, tone: "professional" |
"casual", state: "draft" | "sending" | "outcome_unknown" | "sent", sources: Source[], criticConfidence:
number | null, reviewReasons: ReviewReason[], details: Detail[], egress: EgressRecord[], generatedAt,
updatedAt, sentAt }`. `ComposeSummary`: `{ id, to, subject, preview, state, updatedAt, sentAt, details }`.

**`GET /compose`** — `{ drafts: ComposeSummary[], sent: ComposeSummary[] }`, newest first (sent: last 50).
**`POST /compose`** — 201 `ComposeDraftView`. Body (all optional): `{ to?: string[] (≤20, each ≤320),
cc?, subject? (≤300), brief? (≤4000), body? (≤20000), tone? }`. 409 `too_many_drafts` past 200 unsent.
**`GET /compose/{id}`** — `ComposeDraftView` with its privacy receipt.
**`PATCH /compose/{id}`** — save the given fields (same body). 409 `send_in_progress` / `already_sent`
once a send has started or finished.
**`DELETE /compose/{id}`** — 204 (a sent one too: it leaves the list; its masked copy for the waiting list
stays). 409 `send_in_progress` while a send may still have gone out.
**`POST /compose/{id}/write`** — save the given fields, then write the body (and a subject when none is
set) from the brief and the user's documents. 422 `empty` without a brief · 422 `draft_refused` ·
409 `conflict` when the draft was changed elsewhere (or sent) while it was being written ·
503 `agent_unavailable` / `masking_unavailable` / `private_model_unavailable`. Generation rate limit.
**`POST /compose/{id}/refine`** — the same body plus `instruction` (1..2000): revise the body. Same errors.
**`POST /compose/{id}/send`** — `{ to: string[] (1..20), cc?: string[], subject (1..300), body
(1..20000), remindIfNoReply?: boolean }`: the approved email, sent once from the user's Gmail as a new
thread. A draft already sent answers its view (idempotent). 422 `invalid_recipients` / `no_recipients` /
`no_subject` / `empty` / `unresolved_placeholders` / `redaction_markers` before anything is claimed ·
403 `send_not_granted` · 409 `send_in_progress` · 502 `send_failed` (released, can be sent again) ·
`send_outcome_unknown` (kept claimed; the draft is `outcome_unknown` at once, and any other claim after
10 minutes). Send rate limit.
**`POST /compose/{id}/outcome`** — `{ outcome: "sent" | "not_sent" }`, only while `outcome_unknown`
(409 `conflict` otherwise): the user checked Gmail's Sent folder.

### Agent: new emails (internal, backend to agent on :8001)

**`POST /compose`** — `ComposeRequest { brief, subject, recipients: string[] (placeholders), rag_context,
tone, sign_off, style_hint, style_examples, provider }` → `ComposeResponse { subject, draft, confidence,
issues, attempts, needs_human_review, grounding_ok, pii_clean, tone_match, completeness, pii_findings,
unsupported_specifics, unaddressed_requests, review_reasons, review_codes, model_calls, egress,
prompt_version }`. The reply's critic, PII scan, figures check and repair rounds, judged against the brief.
**`POST /compose/refine`** — `ComposeRefineRequest` (the above plus `draft`, `instruction`) →
`ComposeResponse`. Both need `X-AIMail-Agent-Token`; 422/503/504 as `/process-email`.

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

> **Backend to agent (2026-10-08):** the request and response models live in one module both sides import,
> `backend/app/agent_contract.py`; the backend validates every agent answer against them. `provider` is required.
> `POST /emails/{id}/refine` takes an optional `tone` (`professional` | `casual`, default professional), which the
> agent now keeps through the revision and its review; refine also reports the email's own review reasons
> (possible phishing, no policy context), as drafting does.
