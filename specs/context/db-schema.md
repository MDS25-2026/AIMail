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
| `generated_at` | `TIMESTAMPTZ NULL` | Lane C | when cached; NULL = not generated yet |
| `sent_at` | `TIMESTAMPTZ NULL` | backend | when the approved reply was sent (migration 0005) |
| `created_at` | `TIMESTAMPTZ DEFAULT now()` | default | |

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

> _Other tables below are still TODO. Add them as feature specs land._

### TODO

- [ ] `user` — connected Gmail account, style profile pointer.
- [ ] `thread` — Gmail thread metadata.
- [ ] `chat` — one row per email thread treated as an LLM conversation. Holds the running context the agent pipeline reads on each new message in the thread. FK → `thread`.
- [ ] `conversation` — one row per LLM generation event (subtable of `chat`). Stores: prompt sent, context window included, model used, raw AI response, rubric score, version label. Multiple rows per `chat` allow self-evaluation loop (2–3 revisions before user sees output) and multi-version offerings (showing the user 2–3 drafts to pick from). FK → `chat`.
- [ ] `draft` — generated reply drafts surfaced to the user, status, audit trail. FK → `chat` and the chosen `conversation` row.
- [ ] `draft_feedback` — user thumbs up/down + which version they picked + their final edited text. Drives model-selection learning. FK → `draft`.
- [ ] `style_profile` — per-user writing-style features and embeddings.
- [ ] `email_embedding` — pgvector index over historical replies for retrieval.

> The `chat` → `conversation` parent/child shape is the memory backbone: each new email in a thread reuses the prior `conversation` rows as context, which is what gives the agent its "attention span" across replies. See [`../agent-pipeline.md`](../agent-pipeline.md) for how these tables are read and written during a generation.
