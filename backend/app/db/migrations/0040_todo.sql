-- To-do (specs/features/todo-page.md): replies the user sent, to know who has not answered.

-- Kept apart from messages on purpose: nothing that reads messages (the drafter, the inbox, search)
-- can mistake a sent reply for received mail. Masked like messages; no recipient address is kept.
CREATE TABLE IF NOT EXISTS sent_message (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  -- NULL for the original mailbox's unowned rows, like messages.user_id.
  user_id      UUID REFERENCES user_profile(id) ON DELETE CASCADE,
  -- Gmail's id when known (the listener's Sent watch, or a send from AIMail); NULL for a backfilled send.
  gmail_id     TEXT UNIQUE,
  -- The received email a send from AIMail answered; NULL for a reply written in Gmail.
  message_id   UUID UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
  thread_id    TEXT,
  sent_at      TIMESTAMPTZ NOT NULL,
  subject      TEXT NOT NULL DEFAULT '',
  body_masked  TEXT NOT NULL DEFAULT '',
  -- TRUE when the user asked to be reminded whatever it says; NULL lets the rules decide.
  remind       BOOLEAN,
  dismissed_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sent_message_thread_idx ON sent_message (thread_id, sent_at DESC);
ALTER TABLE sent_message ENABLE ROW LEVEL SECURITY;

-- "No reply needed": out of the to-do lists, still in the inbox.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS dismissed_at TIMESTAMPTZ;
-- Working days before a reply counts as waiting too long.
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS waiting_days SMALLINT NOT NULL DEFAULT 3
  CHECK (waiting_days BETWEEN 1 AND 30);

-- Replies already sent from AIMail, so the waiting list does not start empty.
INSERT INTO sent_message (user_id, message_id, thread_id, sent_at, subject, body_masked)
SELECT m.user_id, m.id, m.thread_id, m.sent_at, coalesce(m.subject, ''), coalesce(m.draft_reply, '')
FROM messages m
WHERE m.sent_at IS NOT NULL AND m.thread_id IS NOT NULL
ON CONFLICT DO NOTHING;
