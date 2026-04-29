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

> _None defined yet. Add tables below as feature specs land._

### TODO

- [ ] `user` — connected Gmail account, style profile pointer.
- [ ] `thread` — Gmail thread metadata.
- [ ] `email` — individual messages within a thread (masked + raw, with the raw stored encrypted).
- [ ] `chat` — one row per email thread treated as an LLM conversation. Holds the running context the agent pipeline reads on each new message in the thread. FK → `thread`.
- [ ] `conversation` — one row per LLM generation event (subtable of `chat`). Stores: prompt sent, context window included, model used, raw AI response, rubric score, version label. Multiple rows per `chat` allow self-evaluation loop (2–3 revisions before user sees output) and multi-version offerings (showing the user 2–3 drafts to pick from). FK → `chat`.
- [ ] `draft` — generated reply drafts surfaced to the user, status, audit trail. FK → `chat` and the chosen `conversation` row.
- [ ] `draft_feedback` — user thumbs up/down + which version they picked + their final edited text. Drives model-selection learning. FK → `draft`.
- [ ] `style_profile` — per-user writing-style features and embeddings.
- [ ] `email_embedding` — pgvector index over historical replies for retrieval.

> The `chat` → `conversation` parent/child shape is the memory backbone: each new email in a thread reuses the prior `conversation` rows as context, which is what gives the agent its "attention span" across replies. See [`../agent-pipeline.md`](../agent-pipeline.md) for how these tables are read and written during a generation.
