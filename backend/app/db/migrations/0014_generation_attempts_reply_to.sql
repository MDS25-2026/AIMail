-- Audit follow-ups.
-- generation_attempts: the pre-generation poller took the same two failing rows every cycle and
-- starved the rest (the listener's quarantine had the same bug, fixed in 0013).
-- reply_to: an approved reply goes to Reply-To when the sender set one; the approver must be able
-- to see that address before clicking, not only From. An identifier like from_addr: never sent to
-- a model.
-- The indexes serve the admin console's window queries.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS generation_attempts INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS reply_to TEXT;

CREATE INDEX IF NOT EXISTS messages_generated_at_idx ON messages (generated_at);
CREATE INDEX IF NOT EXISTS audit_log_created_at_idx ON audit_log (created_at);
