-- Opening an email no longer waits for its draft (app/jobs.py, request_draft): the request is recorded
-- here and the worker drafts requested emails first, within seconds. The index keeps that poll cheap.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS draft_requested_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS messages_draft_requested
    ON messages (draft_requested_at) WHERE draft_requested_at IS NOT NULL AND generated_at IS NULL;
