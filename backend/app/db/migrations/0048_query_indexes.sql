-- Indexes for the inbox, sender search and the unread-attachment note, and a quieter live-inbox
-- trigger. Each index was checked usable with EXPLAIN on synthetic data (200k emails, 20 owners),
-- not measured on a real mailbox: confirm with EXPLAIN ANALYZE there before relying on them.

-- 0046's trigger fired on any UPDATE naming a listed column, even one writing the same value back
-- (UPDATE OF lists columns in the statement, not columns that changed). A WHEN that reads OLD is not
-- allowed on an INSERT trigger, so INSERT and UPDATE are now two triggers on the same function.
DROP TRIGGER IF EXISTS trg_notify_mailbox_change ON messages;
DROP TRIGGER IF EXISTS trg_notify_mailbox_insert ON messages;
CREATE TRIGGER trg_notify_mailbox_insert
AFTER INSERT ON messages
FOR EACH ROW EXECUTE FUNCTION notify_mailbox_change();

DROP TRIGGER IF EXISTS trg_notify_mailbox_update ON messages;
CREATE TRIGGER trg_notify_mailbox_update
AFTER UPDATE OF draft_reply, ai_summary, category, language, read_at, sent_at,
                snoozed_until, dismissed_at, auth_status, masking_status
ON messages
FOR EACH ROW
WHEN (OLD.draft_reply IS DISTINCT FROM NEW.draft_reply
      OR OLD.ai_summary IS DISTINCT FROM NEW.ai_summary
      OR OLD.category IS DISTINCT FROM NEW.category
      OR OLD.language IS DISTINCT FROM NEW.language
      OR OLD.read_at IS DISTINCT FROM NEW.read_at
      OR OLD.sent_at IS DISTINCT FROM NEW.sent_at
      OR OLD.snoozed_until IS DISTINCT FROM NEW.snoozed_until
      OR OLD.dismissed_at IS DISTINCT FROM NEW.dismissed_at
      OR OLD.auth_status IS DISTINCT FROM NEW.auth_status
      OR OLD.masking_status IS DISTINCT FROM NEW.masking_status)
EXECUTE FUNCTION notify_mailbox_change();

-- has_unread_attachment (app/attachment_notes.py): an owner's failed attachment reads, without
-- scanning every audit row of theirs for the Gmail id.
CREATE INDEX IF NOT EXISTS audit_log_user_action_idx ON audit_log (user_id, action);

-- Sender search (app/inbox_search.py) matches from_addr ILIKE '%word%', which no btree can serve.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS messages_from_addr_trgm_idx ON messages USING gin (from_addr gin_trgm_ops);

-- The inbox pages by conversation (app/dashboard.py list_dashboard_emails): DISTINCT ON this exact
-- expression, newest first; it must match _thread_key() as SQLAlchemy writes it. At 10k emails per
-- owner the planner still preferred a bitmap scan and sort: drop it if a real mailbox agrees.
CREATE INDEX IF NOT EXISTS messages_user_thread_key_idx
  ON messages (user_id, (coalesce(thread_id, CAST(id AS TEXT))), created_at DESC, id DESC);
