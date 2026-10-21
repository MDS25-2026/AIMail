-- Live inbox (specs/features/live-inbox.md): every change to an email is announced on the
-- mailbox_changed channel, so the backend can tell the open dashboard at once instead of it polling.
-- Ids only: a NOTIFY payload is readable by every session on the channel and may end up in logs.
CREATE OR REPLACE FUNCTION notify_mailbox_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    kind TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        kind := 'new';
    ELSIF NEW.draft_reply IS DISTINCT FROM OLD.draft_reply THEN
        kind := 'draft';
    ELSE
        kind := 'state';
    END IF;
    PERFORM pg_notify('mailbox_changed',
                      json_build_object('user_id', NEW.user_id, 'message_id', NEW.id, 'kind', kind)::text);
    RETURN NULL;
END;
$$;

-- The columns a dashboard shows or sorts by; an embedding or a classifier score changing is not news.
DROP TRIGGER IF EXISTS trg_notify_mailbox_change ON messages;
CREATE TRIGGER trg_notify_mailbox_change
AFTER INSERT OR UPDATE OF draft_reply, ai_summary, category, language, read_at, sent_at,
                          snoozed_until, dismissed_at, auth_status, masking_status
ON messages
FOR EACH ROW EXECUTE FUNCTION notify_mailbox_change();
