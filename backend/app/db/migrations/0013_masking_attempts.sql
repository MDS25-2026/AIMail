-- #109 follow-up: the re-mask loop kept retrying the same first 20 pending rows, so one message
-- that never masks (or was deleted from Gmail) stalled every message behind it. Attempts are now
-- counted, fewest-tried first, and a row that keeps failing is abandoned: counted on the admin
-- console, its content never stored.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS masking_attempts INT NOT NULL DEFAULT 0;

ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_masking_status_check;
ALTER TABLE messages
  ADD CONSTRAINT messages_masking_status_check
  CHECK (masking_status IN ('complete', 'pending', 'abandoned'));
