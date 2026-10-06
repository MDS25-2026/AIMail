-- Private mode (specs/features/local-model.md): this user's emails are drafted, refined and
-- translated by the company's local model instead of Gemini.
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS draft_provider TEXT NOT NULL DEFAULT 'gemini'
  CHECK (draft_provider IN ('gemini', 'local'));
