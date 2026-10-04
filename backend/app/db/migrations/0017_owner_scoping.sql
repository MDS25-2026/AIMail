-- Per-user mailboxes, step 3 (specs/features/per-user-mailboxes.md, audit findings 2, 3 and 6).
-- Additive except one swap: document.source becomes unique per owner instead of globally.
-- NULLS NOT DISTINCT (Postgres 15+) keeps the unowned rows of the original mailbox deduplicated.

-- Each user's own knowledge base. NULL is the original single mailbox's.
ALTER TABLE document ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES user_profile(id) ON DELETE CASCADE;
ALTER TABLE document DROP CONSTRAINT IF EXISTS document_user_source_key;
ALTER TABLE document ADD CONSTRAINT document_user_source_key UNIQUE NULLS NOT DISTINCT (user_id, source);
ALTER TABLE document DROP CONSTRAINT IF EXISTS document_source_key;

-- Gmail ids are per mailbox. The global key stays until every listener upserts on this one
-- (removed in step 5), or a listener still using on_conflict=gmail_message_id would fail.
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_user_gmail_message_key;
ALTER TABLE messages ADD CONSTRAINT messages_user_gmail_message_key UNIQUE NULLS NOT DISTINCT (user_id, gmail_message_id);

CREATE INDEX IF NOT EXISTS messages_user_created_idx ON messages (user_id, created_at DESC);
