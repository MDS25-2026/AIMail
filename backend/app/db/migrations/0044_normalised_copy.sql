-- Normalisation v2 (specs/features/normalisation-v2.md): each email's language, and an English copy of a
-- non-English one (its subject and the sender's own text, masked like the original) for every step that
-- reads mail. Retention clears own_text_en with the body.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS language TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS subject_en TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS own_text_en TEXT;
-- The worker's queue: emails not yet normalised.
CREATE INDEX IF NOT EXISTS messages_language_pending_idx ON messages (created_at) WHERE language IS NULL;
