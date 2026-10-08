-- Only a send the send path itself marked "outcome unknown" is reconciled against Gmail (app/send_reconciler.py).
-- A sent row with no message id but no mark (old sends, sent before message ids were recorded) is left sent:
-- never resending is the safe default. The first reconciler wrongly released nine such replies on 2026-10-08;
-- they were restored from Gmail the same day.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS send_outcome_unknown_at TIMESTAMPTZ;
ALTER TABLE holding_reply ADD COLUMN IF NOT EXISTS send_outcome_unknown_at TIMESTAMPTZ;
DROP INDEX IF EXISTS messages_unconfirmed_send_idx;
CREATE INDEX IF NOT EXISTS messages_send_unknown_idx ON messages (send_outcome_unknown_at)
    WHERE send_outcome_unknown_at IS NOT NULL;
