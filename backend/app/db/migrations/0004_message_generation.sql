-- Cache Lane C generation on the message so opening an email serves stored text instead of
-- re-running the ~15-60s pipeline every time. generated_at NULL means "not generated yet".

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS ai_summary TEXT,
  ADD COLUMN IF NOT EXISTS draft_reply TEXT,
  ADD COLUMN IF NOT EXISTS action_items JSONB,
  ADD COLUMN IF NOT EXISTS critic_confidence REAL,
  ADD COLUMN IF NOT EXISTS generated_at TIMESTAMPTZ;
