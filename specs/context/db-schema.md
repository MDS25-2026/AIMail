# Database schema

This file is the **source of truth** for the AImail Postgres schema. The actual SQL migrations live in `backend/app/db/migrations/` (TODO), but the canonical description of every table, column, index, and vector dimension lives here.

## Rules

- Add a table here **before** writing the migration.
- Update this file in the same PR that adds, removes, or alters a column.
- Vector columns must include the embedding model and dimension.

## Conventions

- Engine: PostgreSQL 16 with the `pgvector` extension.
- Naming: `snake_case` for tables and columns; tables singular (`user`, not `users`) — TBD, lock in with the first migration.
- Every table has `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`, `created_at TIMESTAMPTZ DEFAULT now()`, `updated_at TIMESTAMPTZ DEFAULT now()`.
- Soft-delete via `deleted_at TIMESTAMPTZ NULL` where relevant.

## Tables

### RAG: policy grounding (Lane B)

The canonical three-table split from [`../features/rag-retrieval.md`](../features/rag-retrieval.md). Separated so a model swap re-embeds without re-chunking, and so a replaced/deleted source is auditable. All follow the conventions above unless noted.

**`document`** — one row per uploaded source (policy PDF, later past-sent-email corpus).

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID PK` | `gen_random_uuid()` |
| `source` | `TEXT NOT NULL` | filename or URL; **unique**, to support replace-on-reupload |
| `title` | `TEXT` | display title (`source_title` in Seam 2) |
| `doc_type` | `TEXT` | e.g. `policy`; reserved for a future past-sent-email type |
| `uploaded_at` | `TIMESTAMPTZ DEFAULT now()` | |
| `created_at` / `updated_at` | `TIMESTAMPTZ DEFAULT now()` | |

**`chunk`** — the retrieval unit.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID PK` | |
| `document_id` | `UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE` | |
| `chunk_idx` | `INT NOT NULL` | order within the document |
| `content` | `TEXT NOT NULL` | |
| `token_count` | `INT` | |
| `metadata` | `JSONB` | for future pre-filtering by `doc_type`/recency |
| `created_at` / `updated_at` | `TIMESTAMPTZ DEFAULT now()` | |

**`embedding`** — per-model vector. **Append-only** (re-embed = new row), so no `updated_at`.

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID PK` | |
| `chunk_id` | `UUID NOT NULL REFERENCES chunk(id) ON DELETE CASCADE` | |
| `embedding` | `vector(1536)` | `gemini-embedding-001`, L2-normalized. **1536 is pinned by pgvector's 2000-dim HNSW cap** — see `docs/decisions/lane-b-ml.md`. |
| `model_name` | `TEXT NOT NULL` | so a model swap is a clean re-embed |
| `created_at` | `TIMESTAMPTZ DEFAULT now()` | |

Index: `CREATE INDEX ON embedding USING hnsw (embedding vector_cosine_ops);`

### Per-user mailboxes: mailbox_connection (migration 0016)

One row per user who connected their Gmail (`specs/features/per-user-mailboxes.md`). RLS on, no
policies.

| Column | Type | Notes |
|--------|------|-------|
| `user_id` | `UUID PK` | Supabase auth user id; FK to `user_profile(id)`, which shares the same id; cascades on delete |
| `provider` | `TEXT NOT NULL` | `gmail` (CHECK); room for `outlook` |
| `email` | `TEXT UNIQUE NOT NULL` | the mailbox address Google reported |
| `refresh_token_encrypted` | `BYTEA NOT NULL` | AES-256-GCM: version byte, 12-byte nonce, ciphertext+tag; user id bound as associated data (`app/core/token_crypt.py`, `listener/tokencrypt.go`) |
| `scopes` | `TEXT[]` | as granted |
| `history_id` | `BIGINT NULL` | per-mailbox `history.list` baseline |
| `watch_expires_at` | `TIMESTAMPTZ NULL` | renew before Gmail's seven-day expiry |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

`messages.user_id` (migration 0007) is now mapped in the ORM; it stays nullable until the backfill.

### Owner scoping (migration 0017)

- `document.user_id UUID NULL` (FK `user_profile`, cascade): each user's own knowledge base.
  Uniqueness is `UNIQUE NULLS NOT DISTINCT (user_id, source)`; the global `document_source_key` is
  dropped, so two users may both upload `policy.pdf`.
- `messages`: `UNIQUE NULLS NOT DISTINCT (user_id, gmail_message_id)` added (Gmail ids are per
  mailbox). The global `messages_gmail_message_id_key` stays until every listener upserts on the
  new key; step 5 drops it.
- Index `messages_user_created_idx (user_id, created_at DESC)` serves each user's inbox.
- **NULL owner** means the original single mailbox (`app/core/mailbox.py`). Those rows are visible
  only to that mailbox's account, and move to it (`user_id` set) when it connects with Google.

### Restorable masking: messages.pii_vault (migration 0018)

`messages.pii_vault BYTEA NULL`: the email's placeholder-to-value map (`{"[PERSON_1]": "Aisyah"}`)
as JSON, sealed with `PII_VAULT_KEY` (AES-256-GCM, `app/core/sealed_box.py`), associated data
`aimail-pii-vault:v1:<user_id or "">:<gmail_message_id>`. Written by the listener with the masked
row; opened only by the backend, per request. NULL for rows from before this, quarantined rows, and
once the daily job (`app/vault_retention.py`) empties it: 30 days after arrival
(`VAULT_RETENTION_DAYS`) or 7 days after the reply was sent. `draft_reply` always holds placeholders,
never the details themselves.

### Row-level security (migration 0015)

Every application table has RLS **on with no policies** (2026-10-04). Supabase's REST API serves
public-schema tables to anyone holding the publishable key, and to any signed-in user's token,
unless RLS is on; before 0015 that key alone read stored emails. With no policy, the anon and
authenticated roles see nothing. The backend connects as `postgres` and the listener uses the
`service_role` key; both bypass RLS. **Every new table must enable RLS in its own migration.**

### Ingestion: messages + audit_log (Lane A writes, Lane B annotates)

One `messages` row per ingested email. **Lane A (JiaJun's Go listener) inserts into a table named
`messages` (not `email`) and `audit_log` via the Supabase PostgREST API**, so the Lane-A column names
below must match his `StoredMessage` Go struct exactly. **Lane B (classifier) writes the priority
columns** later; they are nullable until the email is scored. Neither table is created by the
listener — a migration must create `messages` + `audit_log` in Supabase before ingestion works.

**`messages`**

| Column | Type | Written by | Notes |
|--------|------|-----------|-------|
| `id` | `UUID PK` | default | `gen_random_uuid()` |
| `gmail_message_id` | `TEXT UNIQUE` | Lane A | dedupe key; listener upserts with `on_conflict` so repeat Gmail notifications don't duplicate (migration 0003) |
| `thread_id` | `TEXT NULL` | Lane A | Gmail's `threadId` — the provider's conversation grouping key, **not** `gmail_message_id`. Required to send a reply into the thread, and the key the Chrome extension has from the Gmail URL (migration 0009) |
| `rfc822_message_id` | `TEXT NULL` | Lane A | this message's RFC 5322 `Message-ID` header, angle brackets included. The portable thread identity; becomes the reply's `In-Reply-To` (migration 0009) |
| `thread_refs` | `TEXT NULL` | Lane A | raw `References` header — the ancestry chain. A reply's `References` is this value plus `rfc822_message_id` (RFC 5322 §3.6.4). Named `thread_refs` because `references` is a reserved SQL keyword (migration 0009) |
| `from_addr` | `TEXT` | Lane A | |
| `subject` | `TEXT` | Lane A | |
| `body_masked` | `TEXT` | Lane A | **the masked body — Seam 1, what Lane B reads.** Name is `body_masked`, NOT `masked_body`. |
| `snippet_masked` | `TEXT` | Lane A | |
| `emails_masked` | `INT` | Lane A | count of redactions |
| `phones_masked` | `INT` | Lane A | count of redactions |
| `received_at` | `TIMESTAMPTZ` | Lane A | |
| `importance` | `SMALLINT NULL` | Lane B | 0/1/2 = LOW/MEDIUM/HIGH |
| `importance_confidence` | `REAL NULL` | Lane B | 0..1 |
| `deadline_at` | `TIMESTAMPTZ NULL` | Lane B | extracted deadline |
| `importance_model_version` | `TEXT NULL` | Lane B | clean re-score on retrain |
| `ai_summary` | `TEXT NULL` | Lane C | cached generation (migration 0004) |
| `draft_reply` | `TEXT NULL` | Lane C | cached generation |
| `action_items` | `JSONB NULL` | Lane C | cached generation |
| `critic_confidence` | `REAL NULL` | Lane C | cached generation |
| `critic_attempts` | `SMALLINT NULL` | Lane C | how many refine rounds the critic forced before the draft passed. The only observable evidence the review gate ever engages — a draft rescued by refinement is indistinguishable from a first-pass success without it (migration 0008) |
| `critic_checks` | `JSONB NULL` | Lane C | the review gate's result: `grounding_ok`, `pii_clean`, `tone_match`, `completeness`, `pii_findings`, `review_reasons`, and `model_calls` (one `{model, outcome, ms}` per Gemini attempt; outcomes and timings only, never content) (migration 0010) |
| `needs_human_review` | `BOOLEAN NULL` | Lane C | true when `review_reasons` is non-empty; stored so the dashboard filters without unpacking JSON (migration 0010) |
| `rag_sources` | `JSONB NULL` | backend | the policy chunks the cached draft was grounded on, `[{label, chunkId, excerpt, score}]`, captured at generation so the reviewer sees what the model saw (migration 0011) |
| `generated_at` | `TIMESTAMPTZ NULL` | Lane C | when cached; NULL = not generated yet |
| `sent_at` | `TIMESTAMPTZ NULL` | backend | when the approved reply was sent (migration 0005) |
| `read_at` | `TIMESTAMPTZ NULL` | backend | first time the detail view was opened; NULL = unread. Set once, so it records first read rather than latest (migration 0006) |
| `user_id` | `UUID NULL FK` | backend | mailbox owner. Nullable: one mailbox today, so multi-user is a backfill rather than schema surgery (migration 0007) |
| `sent_message_id` | `TEXT NULL` | backend | the `Message-ID` Gmail assigned to the backend's outgoing reply, read back after `messages.send` rather than assumed. Without it the thread graph breaks at every AImail hop — an incoming reply's `In-Reply-To` points here and matches nothing (migration 0009) |
| `masking_status` | `TEXT NOT NULL DEFAULT 'complete'` | Lane A | `complete`; `pending` for a quarantined row with no content because NER masking was unavailable (#109), completed by the listener when Presidio recovers; `abandoned` when it gave up. Nothing reads or drafts from a row that is not complete (migrations 0012, 0013) |
| `masking_attempts` | `INT NOT NULL DEFAULT 0` | Lane A | failed re-mask attempts; the loop works fewest-first and abandons a row at 12 (migration 0013) |
| `created_at` | `TIMESTAMPTZ DEFAULT now()` | default | |

Index `thread_id` — every planned consumer (thread view, sent-mail indexing, the extension's
lookup from the Gmail URL) groups by it.

Constructing a threaded reply needs all three Lane-A fields plus the Gmail API's `threadId`
parameter: header-only threading leaves Gmail's own UI ungrouped, and `threadId`-only threading
leaves the recipient's client ungrouped. Both mechanisms, or it is not threaded.

**`audit_log`** — Lane A masking/handling audit (JiaJun's `AuditLogEntry`).

| Column | Type | Notes |
|--------|------|-------|
| `id` | `UUID PK` | |
| `action` | `TEXT` | |
| `detail` | `TEXT` | |
| `success` | `BOOLEAN` | |
| `created_at` | `TIMESTAMPTZ DEFAULT now()` | |

> Provisional — confirm exact names/types against JiaJun's Go structs at the sync. Lane A writes via
> PostgREST (`SUPABASE_SERVICE_KEY`); Lane B reads via asyncpg (`DATABASE_URL`). Same Supabase project.

### Personalisation (Lane B, migration 0007)

Applied **after** the classifier predicts, never inside it — see `backend/app/personalisation.py`.
The model stays text-only so its macro-F1 against the holdout stays comparable however a user
configures things. Keyed by user throughout though one mailbox runs today.

**Precedence, most specific first:** `sender_rule` → `keyword_rule` → model prediction shifted by
`priority_bias` → medium when unscored. An unscored message ignores the bias: a preference must
not manufacture a priority the classifier never produced.

**Prompt boundary:** `sender_rule` and `keyword_rule` are lookups and must **never** be
interpolated into a prompt. `user_profile.responsibilities` is the one exception and reaches
drafting only, never classification.

**`user_profile`** — the mailbox owner, keyed by `email` since that is the identifier every lane
already shares. Holds `display_name`, `role`, `responsibilities`.

**`user_preferences`** — one row per user. `priority_bias` (`SMALLINT`, −1/0/+1, constrained),
`default_sort` (`date|priority|deadline|confidence`, constrained), `default_tone`. Defaults
reproduce current behaviour exactly, so an unconfigured user sees no change.

The bias is three-valued deliberately: it is derived from a handful of calibration judgements, and
anything finer would be fitting noise. Do not "improve" it into per-class weights without data.

**`sender_rule`** — `(user_id, from_addr)` PK, `priority` 0/1/2. Matched as a **substring** of the
From header, because a real header is `Name <addr>` and equality would never fire.

**`keyword_rule`** — `(user_id, keyword)` PK, `priority` 0/1/2. Matched against subject + body,
lowercased.

> _Other tables below are still TODO. Add them as feature specs land._

### TODO

- [x] `user_profile` — shipped in migration 0007 (see Personalisation above). A connected-Gmail-account table is still needed for real multi-user.
- [ ] `thread` — Gmail thread metadata. `messages.thread_id` (migration 0009) already holds Gmail's
      `threadId` as a natural key, so normalising into this table is a backfill plus an FK, not a
      migration against a column the listener writes. Same shape as `messages.user_id` in 0007.
- [ ] `chat` — one row per email thread treated as an LLM conversation. Holds the running context the agent pipeline reads on each new message in the thread. FK → `thread`.
- [ ] `conversation` — one row per LLM generation event (subtable of `chat`). Stores: prompt sent, context window included, model used, raw AI response, rubric score, version label. Multiple rows per `chat` allow self-evaluation loop (2–3 revisions before user sees output) and multi-version offerings (showing the user 2–3 drafts to pick from). FK → `chat`.
- [ ] `draft` — generated reply drafts surfaced to the user, status, audit trail. FK → `chat` and the chosen `conversation` row.
- [ ] `draft_feedback` — user thumbs up/down + which version they picked + their final edited text. Drives model-selection learning. FK → `draft`.
- [ ] `style_profile` — per-user writing-style entries; proposed as `style_entry` in [`../features/writing-profile.md`](../features/writing-profile.md).
- [ ] `holding_reply_settings`, `holding_reply`, `messages.is_automated` — proposed in [`../features/holding-reply.md`](../features/holding-reply.md).
- [ ] `email_embedding` — pgvector index over historical replies for retrieval.

> The `chat` → `conversation` parent/child shape is the memory backbone: each new email in a thread reuses the prior `conversation` rows as context, which is what gives the agent its "attention span" across replies. See [`../agent-pipeline.md`](../agent-pipeline.md) for how these tables are read and written during a generation.
