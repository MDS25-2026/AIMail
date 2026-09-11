-- Per-user personalisation. The classifier stays text-only and unchanged; everything personal is
-- applied AFTER prediction by the policy layer (app/personalisation.py), so the model's macro-F1
-- against the holdout remains comparable while the ranking a user sees is their own.
--
-- Keyed by user throughout, though the system currently runs one mailbox. That is deliberate:
-- multi-user then becomes a backfill rather than schema surgery.

CREATE TABLE IF NOT EXISTS user_profile (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email            TEXT NOT NULL UNIQUE,   -- mailbox owner, the natural key across lanes
    display_name     TEXT,
    role             TEXT,                   -- e.g. "Procurement Lead"
    responsibilities TEXT,                   -- short paragraph, injected into drafting prompts only
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per user. Defaults reproduce today's behaviour exactly, so an unconfigured user sees
-- no change: neutral bias, newest-first, which is the classifier offered rather than imposed.
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id       UUID PRIMARY KEY REFERENCES user_profile(id) ON DELETE CASCADE,
    priority_bias SMALLINT NOT NULL DEFAULT 0,       -- -1, 0 or +1, coarse on purpose (see below)
    default_sort  TEXT NOT NULL DEFAULT 'date',      -- date | priority | deadline | confidence
    default_tone  TEXT NOT NULL DEFAULT 'professional',
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT priority_bias_range CHECK (priority_bias BETWEEN -1 AND 1),
    CONSTRAINT default_sort_known CHECK (default_sort IN ('date','priority','deadline','confidence'))
);

-- Exact-match override on the sender address. A lookup, never prompt input.
CREATE TABLE IF NOT EXISTS sender_rule (
    user_id   UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    from_addr TEXT NOT NULL,                 -- lowercased before storage and lookup
    priority  SMALLINT NOT NULL,             -- 0 low, 1 medium, 2 high
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, from_addr),
    CONSTRAINT sender_priority_range CHECK (priority BETWEEN 0 AND 2)
);

-- Same shape for topics: "anything mentioning Project Alpha is high for me".
CREATE TABLE IF NOT EXISTS keyword_rule (
    user_id   UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
    keyword   TEXT NOT NULL,                 -- lowercased, matched against subject + body
    priority  SMALLINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, keyword),
    CONSTRAINT keyword_priority_range CHECK (priority BETWEEN 0 AND 2)
);

-- Nullable so today's single-mailbox rows stay valid. Adding it now means the multi-user step is
-- a backfill, not a migration against a table the listener writes to.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES user_profile(id);

CREATE INDEX IF NOT EXISTS messages_user_id_idx ON messages (user_id);
