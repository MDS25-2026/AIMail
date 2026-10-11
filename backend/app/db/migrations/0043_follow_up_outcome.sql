-- A follow-up whose answer from Gmail was lost is marked, like a reply (0028), so the reconciler can ask Gmail
-- and release the claim if it never went (app/send_reconciler.py). Before this the claim stayed for good.
ALTER TABLE sent_message ADD COLUMN IF NOT EXISTS follow_up_outcome_unknown_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS sent_message_follow_up_unknown_idx ON sent_message (follow_up_outcome_unknown_at)
    WHERE follow_up_outcome_unknown_at IS NOT NULL;
