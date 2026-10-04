-- Thread identity, captured at ingestion (docs/decisions/shared.md, 2026-09-09). Gmail threads a
-- reply only when it carries the thread id, In-Reply-To/References and a matching Subject.
--
-- These are identifiers, not content, and are stored unmasked on purpose: a Message-ID looks
-- like an email address, and masking it would break the one thing it exists for. None of them
-- is ever sent to a model.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS thread_id TEXT,
  ADD COLUMN IF NOT EXISTS rfc822_message_id TEXT,
  ADD COLUMN IF NOT EXISTS thread_refs TEXT,
  ADD COLUMN IF NOT EXISTS sent_message_id TEXT;

CREATE INDEX IF NOT EXISTS messages_thread_id_idx ON messages (thread_id);
