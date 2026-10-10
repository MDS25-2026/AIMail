-- Saved reply templates (specs/features/reply-templates.md): personal, stored as the user typed them.
CREATE TABLE IF NOT EXISTS reply_template (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
  title            TEXT NOT NULL,
  body             TEXT NOT NULL,
  language         TEXT NOT NULL CHECK (language IN ('en', 'ms', 'zh')),
  trigger_keywords TEXT[] NOT NULL DEFAULT '{}',
  -- The suggestion picks the most recently used of several matching templates.
  last_used_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS reply_template_user_idx ON reply_template (user_id);

ALTER TABLE reply_template ENABLE ROW LEVEL SECURITY;
