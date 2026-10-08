-- What left for a model, per prompt (model_gateway.Egress): the privacy receipt shows a record, not a claim.
-- No prompt text is stored: purpose, provider, size, digest and hidden-detail counts only.
CREATE TABLE IF NOT EXISTS model_egress (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES user_profile(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
    purpose    TEXT NOT NULL,
    provider   TEXT NOT NULL CHECK (provider IN ('gemini', 'local')),
    chars      INTEGER NOT NULL,
    sha256     TEXT NOT NULL,
    hidden     JSONB NOT NULL DEFAULT '{}'::jsonb,
    caught     INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS model_egress_message_idx ON model_egress (message_id, created_at DESC);
ALTER TABLE model_egress ENABLE ROW LEVEL SECURITY;
