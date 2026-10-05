-- Per-user mailboxes (specs/features/per-user-mailboxes.md, ADR 0005 stage 2): one row per user
-- who connected their Gmail, holding the Google refresh token sealed by app/core/token_crypt.py.
-- user_id is the Supabase auth user id; that user's user_profile row shares the same id, so the
-- existing messages.user_id key (to user_profile) and the personalisation tables keep working.

CREATE TABLE IF NOT EXISTS mailbox_connection (
  user_id                  UUID PRIMARY KEY REFERENCES user_profile(id) ON DELETE CASCADE,
  provider                 TEXT NOT NULL DEFAULT 'gmail' CHECK (provider IN ('gmail')),
  email                    TEXT NOT NULL UNIQUE,
  refresh_token_encrypted  BYTEA NOT NULL,
  scopes                   TEXT[] NOT NULL DEFAULT '{}',
  history_id               BIGINT,
  watch_expires_at         TIMESTAMPTZ,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Never readable through the REST API: no policies, so only the backend (postgres) and the
-- listener (service_role) can reach it (see migration 0015).
ALTER TABLE mailbox_connection ENABLE ROW LEVEL SECURITY;
