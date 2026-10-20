-- Compose (specs/features/compose.md): new emails the user writes, saved until sent or deleted.
-- Text is stored with placeholders; the values of details the user typed sit in pii_vault, sealed
-- like a received email's (bound to the owner and 'compose:<id>'). Addresses are kept as typed: they
-- are needed to send and never reach a model.
CREATE TABLE IF NOT EXISTS compose_draft (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
  to_addrs                 TEXT[] NOT NULL DEFAULT '{}',
  cc_addrs                 TEXT[] NOT NULL DEFAULT '{}',
  subject                  TEXT NOT NULL DEFAULT '',
  brief                    TEXT NOT NULL DEFAULT '',
  body                     TEXT NOT NULL DEFAULT '',
  pii_vault                BYTEA,
  tone                     TEXT NOT NULL DEFAULT 'professional',
  rag_sources              JSONB,
  critic_confidence        REAL,
  critic_attempts          INT NOT NULL DEFAULT 0,
  critic_checks            JSONB,
  needs_human_review       BOOLEAN NOT NULL DEFAULT FALSE,
  generated_at             TIMESTAMPTZ,
  -- Claim-then-send, as for replies: set before Gmail is called, so two clicks send once.
  send_claimed_at          TIMESTAMPTZ,
  -- Set with the claim and cleared when the send is recorded: a crash in between reads as unknown.
  send_outcome_unknown_at  TIMESTAMPTZ,
  sent_at                  TIMESTAMPTZ,
  sent_gmail_id            TEXT,
  sent_thread_id           TEXT,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS compose_draft_user_idx ON compose_draft (user_id, updated_at DESC);
-- Like every table: the API connects as the owner, so PostgREST's anon key can read nothing here.
ALTER TABLE compose_draft ENABLE ROW LEVEL SECURITY;

-- The privacy receipt of a compose draft. SET NULL, not CASCADE: deleting a draft keeps the record
-- that its prompts left, like the egress rows of an erased email's search.
ALTER TABLE model_egress ADD COLUMN IF NOT EXISTS compose_draft_id UUID
  REFERENCES compose_draft(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS model_egress_compose_draft_idx ON model_egress (compose_draft_id)
  WHERE compose_draft_id IS NOT NULL;
