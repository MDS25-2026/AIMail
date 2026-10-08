-- The tone a stored draft was written in (app/dashboard.py), so the view shows the draft's own tone
-- instead of always "professional". NULL for drafts written before this column: shown as professional,
-- the tone every draft used until then.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS draft_tone TEXT;
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_draft_tone_known;
ALTER TABLE messages ADD CONSTRAINT messages_draft_tone_known
    CHECK (draft_tone IS NULL OR draft_tone IN ('professional', 'casual'));
