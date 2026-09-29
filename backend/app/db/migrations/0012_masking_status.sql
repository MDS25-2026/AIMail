-- #109: a message whose masking could not complete is quarantined, not stored degraded. Its row
-- exists (sender, date, thread) with no content until the listener re-masks it. Every existing
-- row was stored complete or degraded before this; they are marked complete, and the degraded
-- ones remain findable through the "(presidio degraded" audit rows and remask_outliers.py.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS masking_status TEXT NOT NULL DEFAULT 'complete';

ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_masking_status_check;
ALTER TABLE messages
  ADD CONSTRAINT messages_masking_status_check CHECK (masking_status IN ('complete', 'pending'));

-- The listener's re-mask loop asks for pending rows every few minutes; almost none ever are.
CREATE INDEX IF NOT EXISTS messages_masking_pending_idx
  ON messages (received_at) WHERE masking_status = 'pending';
