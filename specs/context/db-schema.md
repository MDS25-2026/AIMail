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
- [ ] `draft` — generated reply drafts, status, audit trail.
- [ ] `style_profile` — per-user writing-style features and embeddings.
- [ ] `email_embedding` — pgvector index over historical replies for retrieval.
