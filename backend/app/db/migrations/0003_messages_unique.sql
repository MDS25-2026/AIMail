-- Gmail fires several Pub/Sub notifications per email, so the listener could insert the same
-- message multiple times. Dedupe existing rows (keep the earliest per gmail_message_id), then
-- enforce uniqueness so repeat notifications can't create duplicates.

DELETE FROM messages a
USING messages b
WHERE a.gmail_message_id = b.gmail_message_id
  AND a.gmail_message_id IS NOT NULL
  AND a.ctid > b.ctid;

ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_gmail_message_id_key;

ALTER TABLE messages ADD CONSTRAINT messages_gmail_message_id_key UNIQUE (gmail_message_id);
