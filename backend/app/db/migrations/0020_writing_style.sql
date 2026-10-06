-- Writing style (specs/features/writing-profile.md): how the user writes, in their control.
-- Every text here is stored masked; the raw text the user typed is never kept.

CREATE TABLE IF NOT EXISTS writing_style (
  user_id          UUID PRIMARY KEY REFERENCES user_profile(id) ON DELETE CASCADE,
  description      TEXT NOT NULL DEFAULT '',
  -- Off by default: nothing is recorded from sends until the user switches it on.
  learning_enabled BOOLEAN NOT NULL DEFAULT false,
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS style_example (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
  text       TEXT NOT NULL,
  source     TEXT NOT NULL CHECK (source IN ('pasted', 'sent')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS style_example_user_idx ON style_example (user_id, created_at);

CREATE TABLE IF NOT EXISTS style_habit (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
  kind       TEXT NOT NULL CHECK (kind IN ('greeting', 'signoff', 'length', 'swap')),
  value      TEXT NOT NULL,
  evidence   SMALLINT NOT NULL,
  out_of     SMALLINT NOT NULL,
  -- A habit the user deleted stays as a marker so the learner never brings it back.
  suppressed BOOLEAN NOT NULL DEFAULT false,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, kind, value)
);

-- Written at send time only while learning is on: the draft as shown, and how much it was edited.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS draft_shown TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS edit_ratio REAL;

ALTER TABLE writing_style ENABLE ROW LEVEL SECURITY;
ALTER TABLE style_example ENABLE ROW LEVEL SECURITY;
ALTER TABLE style_habit ENABLE ROW LEVEL SECURITY;
