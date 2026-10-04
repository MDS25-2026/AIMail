# Shared — cross-lane decisions

Schema, CI, seams, the thin slice, and anything touching more than one lane. Everyone logs
here when their change crosses a lane boundary. Schema and public contracts are "ask first"
(both CLAUDE.md files) — log the decision here *and* update `specs/context/` in the same PR.

## Log

### 2026-10-05 — Per-user mailboxes: every row has an owner, every query is scoped to it
- Decision: each user who signs in with Google and grants Gmail access gets a `mailbox_connection`
  row (sealed refresh token, migration 0016). Every email and document query filters on the
  owner (`app/core/ownership.py`); another user's email id answers `404`, like an unknown id.
  `GET /auth/session`'s `hasMailbox` means "has connected Gmail, or owns the original mailbox".
  Rows with no owner are the original `token.json` mailbox's, visible only to its account, and
  move to it when it connects. Knowledge bases are per user (`document.user_id`, migration 0017).
- Why: the owner asked that anyone can sign up and see their own Gmail, and that each user see
  only their own mail (ADR 0005 stage 2; `specs/features/per-user-mailboxes.md`).
- Affects: Lane B (every route), Lane C (none: payloads unchanged), Lane D (`hasMailbox` text,
  `send_not_granted`), Lane A (rows carry `user_id`).
- Status: built by veyroxie on `feat/per-user-mailboxes`; migrations 0016 and 0017 applied.

### 2026-10-05 — `403 send_not_granted`; replies go out from the owner's own Gmail
- Decision: a reply uses its email owner's own refresh token, refreshed with the Google web client
  configured in Supabase (`GOOGLE_OAUTH_CLIENT_ID/SECRET`). A user who granted read but not send
  gets `403 send_not_granted` before anything is claimed. Unowned rows still send via `token.json`.
- Why: Google lets people untick "send" on the consent screen; a 502 would wrongly say "try again".
- Status: built 2026-10-05; live send pending the client secret in `.env`.

### 2026-10-05 — The listener's duplicate key is per mailbox; Pub/Sub auth is interim
- Decision: the listener upserts on `(user_id, gmail_message_id)` (`UNIQUE NULLS NOT DISTINCT`,
  migration 0017), since Gmail ids are only unique per mailbox. The old global
  `messages_gmail_message_id_key` stays until every running listener uses the new key; step 5
  drops it. Pub/Sub still authenticates as the `token.json` account until a service account
  replaces it (audit finding 4). Only one listener should run on the subscription: Pub/Sub splits
  notifications between subscribers, so an old listener would take some users' notifications
  (the per-mailbox baseline recovers them on the next one).
- Affects: Lane A (`listener/mailboxes.go`, `dedupe.go`, `quarantine.go`), for JiaJun's review.
- Status: built 2026-10-05; live run pending the client secret in `.env`.

### 2026-10-04 — Row-level security on every table
- Decision: migration 0015 enables RLS on all nine application tables with no policies, so the
  REST API answers nothing to the publishable key or a user's token. New tables enable it in the
  same migration that creates them.
- Why: found while starting per-user mailboxes. With RLS off, a request using only the publishable
  key returned rows from `messages`, `audit_log` and `document`; verified, then verified blocked
  (0 rows) after applying. The backend (`postgres`) and listener (`service_role`) bypass RLS and
  were checked to still read and write.
- Affects: the database only; no code change. Applied to Supabase 2026-10-04.
- Status: applied by veyroxie.

### 2026-10-04 — Sender name and address are stored unmasked, on purpose
- Decision: `messages.from_addr` and `reply_to` keep the sender's display name and address as
  Gmail gives them. They are personal data under the PDPA, but storing them is necessary for the
  service (the reader must see who wrote, and a reply needs the address), and they never enter a
  model payload: `thread_context` labels earlier messages by position, never by sender.
- Why: the 30 Sep audit listed this as a leak; the mailbox owner decided it is a documented, minimal
  use instead. Masking the name would show "[Redacted]" for every sender in the inbox.
- Revisit when: anything starts sending `from_addr` to a model, or a retention policy is written
  (then these columns follow it like the rest of the row).
- Status: decided by the mailbox owner, 2026-10-04.

### 2026-10-04 — Refined drafts are reviewed like generated ones; typed text is masked
- Decision: Lane C's `/refine` runs the critic, the PII scan and the figures check on the revision
  and returns the same review fields as `/process-email`; the backend stores them with the draft,
  replacing the old verdict. The backend masks fixed formats (email, IC, passport, card with a Luhn
  check, phone) in text the user typed before any model sees it; names stay, by the owner's choice,
  since masking them would fill every refined draft with [Redacted].
- Why: phase 0 of the 30 Sep audit, raised again at meeting 30. A refined draft skipped every check
  while the previous "checked" badge stayed on screen, and typed phone numbers reached Gemini.
- Affects: Lane C (`email_agent.py` `/refine`), Lane B (`app/dashboard.py`, `app/main.py`, new
  `app/core/typed_text.py`). No dashboard change: it already re-reads the stored verdict.
- Status: implemented by veyroxie, 2026-10-04.

### 2026-10-04 — A reply is sent at most once, and the server checks what it sends
- Decision: `send_reply` splits failures by whether Gmail could have acted. Failing to connect, or an
  error status from Gmail, is `SendError` (claim released, can be approved again). A read timeout,
  a cut connection or an unreadable 2xx is `SendOutcomeUnknownError`: the claim is kept, an audit row
  `send_outcome_unknown` is written, and the route answers `504`. `/send` also refuses empty drafts,
  drafts with redaction markers (422) and quarantined emails (409). The marker pattern moved to
  `app/core/redaction.py`, shared with the agent.
- Why: phase 0 of the 30 Sep audit. Any failure after the POST released the claim, so a second
  press sent a second copy; and the dashboard's marker warning could be bypassed by calling the API.
- Affects: Lane B (`app/gmail_send.py`, `app/dashboard.py`, `app/main.py`), Lane C
  (`email_agent.py` imports the shared pattern), Lane D (`lib/api.ts`, `useDraftWorkflow.ts`).
- Status: implemented by veyroxie, 2026-10-04.

### 2026-09-30 — Regenerate and refine report failure instead of returning the old draft
- Decision: both routes raise `DraftNotUpdatedError` when the draft did not change, answered as
  `502 agent_unavailable`, `422 draft_refused` or `409 masking_pending` (see
  `specs/context/api-contracts.md`). `_generate_and_store` returns a `GenerationOutcome` instead
  of a bool, so the caller can tell "no reply needed" from "the agent failed".
- Why: with the agent down, both answered `200` with the unchanged email, so the dashboard said
  "Draft refined" when nothing had happened. Found while verifying the Lane D draft-error fix.
- Affects: Lane B (`app/dashboard.py`, `app/main.py`) and its one consumer, Lane D (already
  handles non-2xx on both routes). No schema change.
- Status: implemented by veyroxie, approved by the mailbox owner 2026-09-30.

### 2026-09-29 — Masking fails closed; admin console on Supabase Auth
- Decision (#109): a message whose NER masking cannot complete is quarantined
  (`messages.masking_status = 'pending'`, no content) and completed by the listener when Presidio
  recovers. Lane B never drafts, refines, translates or scores a pending row; Lane D shows it as
  awaiting masking. Migration 0012 applied.
- Decision (ADR 0004): the admin console authenticates Supabase users with
  `app_metadata.role = "admin"`, tokens held in HttpOnly cookies by the backend. The rest of the
  API keeps the shared token until it moves to the same JWTs.
- Why: the previous "degrade to regex-only" policy stored real names (observed, #109; the admin
  console shows 5 such stores in the last 30 days). The shared token is compiled into the browser
  bundle, so it cannot gate operator data.
- Affects: Lane A (`listener/quarantine.go`, `main.go`), Lane B (`app/admin/`, `app/dashboard.py`,
  `app/main.py` CORS credentials, migration 0012), Lane D (`/admin`, quarantine notice), CI.
- Status: implemented; needs JiaJun's review of the quarantine loop and Elyesa's of the admin API.

### 2026-09-29 — One PR across all four lanes: resilience, reading, normalisation, surfaces
- Decision: a single bundled PR (branch `feat/hackathon-reuse`, stacked on #113) carries work in
  every lane, approved by the mailbox owner on 2026-09-29 as one reviewable unit. The cross-lane
  seams it changes:
  - `DashboardEmail` gains `sources` fields (`chunkId`, `excerpt`, `score`) and `quantities`;
    both additive. `POST /emails/{id}/translate` is new (Lane B route, Lane C `/translate`).
  - Lane C (`email_agent.py`) now imports shared backend modules: `app.core.logging_setup`,
    `app.core.middleware` and `app.normalise`, instead of keeping private copies. The figures gate
    and the translation checks read numbers through the same layer the dashboard does.
  - Lane A's attachment reader is a new local container replacing `presidio-image-redactor`.
  - Migrations 0009 (thread identity) and 0011 (`rag_sources`) are applied.
- Why one PR: the owner's review queue is the bottleneck, and the pieces share contracts (the
  normalisation layer feeds the gate, the dashboard and translation).
- Why the agent imports `app.*` rather than copying: a second copy of number parsing is how the
  gate and the dashboard would come to disagree about what "18.400,00" means.
- Affects: all lanes. Owners to review their folders: JiaJun (`listener/`), Elyesa
  (`backend/app/`), Hanif (`email_agent.py`, `gemini_client.py`), Han (the dashboard).
- Status: implemented; awaiting each owner's review.

### 2026-09-29 — Replies read the original's headers from Gmail at send time
- Decision: the send path reads Subject, From, Reply-To, Message-ID, References and threadId
  from Gmail (`format=metadata`, headers only) when the reply is approved, and sends with
  `threadId`, `In-Reply-To` and `References`. The listener also stores `thread_id`,
  `rfc822_message_id` and `thread_refs` at ingest, per the 2026-09-09 decision, for the thread
  view and the extension. After sending, the backend reads back the `Message-ID` Gmail assigned
  and stores it as `sent_message_id`, which settles that decision's open question without
  relying on Gmail keeping a client-supplied one.
- Why: Gmail threads a reply only when the Subject matches the original's
  (developers.google.com/workspace/gmail/api/guides/threads), and the stored subject is masked.
  Replies were going out as new threads titled "Re: ... [Redacted]". The real subject now lives
  only in memory for the length of the send.
- Why not store the raw subject: it is content, and storing it would break mask-before-storage.
- Affects: Lane A (`listener/thread.go`, `StoredMessage`), Lane B (`app/gmail_send.py`,
  `app/dashboard.py`, `app/db/models.py`), migration 0009 (applied).
- Status: implemented — needs JiaJun's review of the listener change.

### 2026-09-11 — The review gate reads the critic's four checks, not its self-reported score
- Decision: `needs_human_review` is now a conjunction over the checks the critic already computes
  (grounding, PII, completeness) plus a deterministic PII scan of the generated draft and an
  `attempts > 0` term, instead of one comparison against a self-reported scalar. Tone is advisory
  and never blocks. Refine and review thresholds are split (0.8 / 0.9). Confidence is clamped to
  [0,1]. Quoted history is stripped inside `extract_actions()` only.
- Why: measured over 43 drafts, the gate had never fired. The repair loop ran on the same constant
  as the flag, so it resolved anything that would have tripped it, and the four real checks were
  computed and discarded — they appeared nowhere in the code outside the prompt and schema.
  Verified after the change: a draft echoing an email address and phone number, scoring exactly
  0.8, now flags on two independent grounds; under the old comparison it passed.
- Why not just move the threshold: the scalar has no definition and is documented to saturate at
  the ceiling (Xiong et al., ICLR 2024, arXiv 2306.13063 — our values were 0.85/0.9/0.95/1.0,
  their "80-100% in multiples of 5"). Recalibrating leaves the gate reading a number nobody can
  defend in a viva.
- Why the PII scan is deterministic: the draft is generated from masked text, so any format-clear
  PII in it was invented or leaked. Presidio with ad-hoc MY_NRIC and MY_PHONE recognizers, verified
  live against the running analyzer; an unreachable scanner yields `pii_clean: None`, not True.
- Cross-lane: this edits `backend/email_agent.py`, which is Lane C's. Done at the Lane B owner's
  direction without waiting for Hanif; design rationale in
  [`../../specs/features/critic-evaluation-gates.md`](../../specs/features/critic-evaluation-gates.md).
  **Hanif should review and is free to redo any of it** — the seam (`/process-email` response) only
  gained fields, so nothing downstream breaks.
- Affects: `backend/email_agent.py`, `app/dashboard.py`, `app/db/models.py`, migration 0010,
  `Makefile` (lint now covers `email_agent.py`, which neither it nor CI checked before).
  `.github/workflows/ci.yml` still runs `ruff check app tests scripts` and should be brought into
  line — a workflow edit, so left for a separate ask.
- Status: proposed — needs Hanif's review as owner of the file.

### 2026-09-09 — Thread identity is captured at ingestion, not fetched at send
- Decision: `messages` gains `thread_id`, `rfc822_message_id`, `thread_refs` (Lane A, from the
  message the listener already fetches) and `sent_message_id` (backend, for its own replies).
  Migration 0009 — independent of 0006, 0007 and 0008, so no ordering constraint between them.
  (0008 went to `critic_attempts`, which needs no co-sign and could land immediately; these
  columns wait on Lane A.)
- Why: approved replies send as standalone mail because nothing stores what threading needs. Four
  planned items need that identity in the database, not just at send time — sent-mail indexing
  (backlog 2), the thread view (backlog 4), the Chrome extension (Gmail's URL fragment names the
  *thread*, not the message), and the history-ID ingestion fix.
- Why not fetch at send time: cheaper this week — no migration, no cross-lane change — but it
  serves one caller, makes the other three pay their own round trip, and fails if the original is
  deleted. Kept as the fallback if the schedule forces it; the header-construction code is the same
  either way, so it is not throwaway work.
- Naming and shape: `thread_refs` because `references` is a reserved SQL keyword; it holds the whole
  chain, not just the parent's ID, so ancestry survives past depth one (RFC 5322 §3.6.4). Column
  semantics are documented in `specs/context/db-schema.md`.
- Open: confirm Gmail preserves a client-supplied `Message-ID` on `messages.send` before relying on
  `sent_message_id`. Store only these four fields, not the full header block.
- Affects: Lane A (`listener/main.go`, `StoredMessage`), Lane B (`app/gmail_send.py`, `dashboard.py`),
  `specs/context/db-schema.md` (this PR), migration 0009.
- Status: implemented 2026-09-29 (migration 0009 applied). Still needs JiaJun's co-sign as owner
  of the `messages` table and the listener; see the 2026-09-29 entry for what the build settled.

### 2026-08-31 — Seam 1 resolved: canonical column is `messages.body_masked`
- Decision: the masked-email column is `messages.body_masked`; `masked_body` is retired.
  Closes finding 1 of the 2026-08-06 integration-sync entry.
- Why: the code is already unified — the Go struct, migration `0002_messages.sql`, ORM model
  `app/db/models.py`, and every consumer use `body_masked`; `grep -rn masked_body backend
  --include='*.py'` returns nothing. Only docs still carried the old name (audit item 8).
- Why not rename to `masked_body`: Lane A owns the `messages` table and its writer already
  ships `body_masked`; renaming a live column costs a migration plus every consumer, for nothing.
- Affects: Lanes A + B; `specs/context/db-schema.md` (already declared canonical),
  `specs/architecture.md` (Seam-1 row + reconciliation TODO cleared),
  `docs/decisions/lane-a-spine.md` (seam name corrected). Older dated entries naming
  `masked_body` stay verbatim as history.
- Status: accepted — JiaJun co-sign pending as table owner.

### 2026-07-07 — Schema authority order for reconciliation
- Decision: when the pasted research, the repo design specs, and the proposal report
  disagree, resolve as: **proposal R-IDs = fixed contract > repo design specs (in flux) >
  research (one input)**.
- Why: the proposal is the graded, submitted team contract; the repo specs are a scaffold
  that has already drifted (see below); the research is one member's external exploration.
- Affects: `specs/context/db-schema.md`, all lane schemas.
- Status: proposed
- Reference: full reconciled schema drafted in scratchpad (not yet committed to db-schema.md).

### 2026-07-07 — Repo drift found while reading specs (needs team decision)
- Decision: none yet — flagging two stale/contradictory spots.
  1. `specs/architecture.md` describes `Gmail -> n8n -> listener`; proposal moved to
     **Go webhook + Pub/Sub** (Table 3 marks n8n "prototyping only"; `main.go` is a draft
     webhook). Architecture.md needs updating to match, or the migration finished.
  2. ADR 0001 "no chrome extension" contradicts **R04.5** (chrome extension required).
- Why logged: both were written into the repo before the proposal's final architecture; a
  new session would trust the stale version.
- Affects: architecture.md, ADR 0001, Lane A + Lane D.
- Status: proposed — raise at next sprint planning.

### 2026-08-06 — Integration sync: divergences found across lane branches
- Context: first sync; `main` still on scaffold, all four lanes on their own branches (none merged).
- Found:
  1. **Seam 1 field mismatch (blocking):** Lane A (JiaJun) persists `body_masked`; Lane B expects
     `masked_body`. Align on one name — recommend `body_masked` (Lane A owns the email table).
  2. **Two frontends:** Han's Vite dashboard vs the Next.js scaffold. Keep Han's; retire the scaffold.
  3. **Two listeners:** JiaJun's Go listener vs the Python stub. Keep Go; retire the stub.
  4. **DB access split:** Lane A writes via Supabase PostgREST (`SUPABASE_SERVICE_KEY`); Lane B reads
     via asyncpg (`DATABASE_URL`). Same project required; column names must match in `db-schema.md`.
  5. **One shared Supabase project** — all lanes must point at the same project or writes/reads never meet.
- Status: proposed — resolve at the sync meeting. Reflected in `specs/architecture.md`.

### 2026-07-30 — Lane B demo endpoints recorded in api-contracts (provisional)
- Decision: documented `/search`, `/ask`, `GET|POST /documents`, `/documents/upload` in
  `specs/context/api-contracts.md` as a **provisional** Lane B demo surface, not the finalised contract.
- Why: they exist in `backend/app/main.py` (the retrieval demo) and were undocumented — real drift.
  Recording them lets Lane C/D see the shapes; final shapes/auth/error-envelope get pinned with Lane D.
- Why not treat as final: they skip the `{error:{...}}` envelope and have no auth; that alignment is a
  follow-up when the contract is agreed.
- Affects: `specs/context/api-contracts.md`, Lane B, Lane D.
- Status: proposed

### 2026-07-07 — Decision-log convention created
- Decision: per-lane append-only logs under `docs/decisions/`, lighter tier below ADRs.
- Why: a lane's rationale trail survives reassignment (build-split reopened ownership);
  one owner per lane makes it effectively per-person without breaking on a swap.
- Why not per-person files: they break the moment a lane is reassigned.
- Affects: repo docs convention.
- Status: accepted
