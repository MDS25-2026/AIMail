-- Background jobs claim rows with a lease (app/jobs.py), so any number of workers can run side by side
-- without drafting the same email twice; a crashed worker's lease simply runs out.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS generation_claimed_until TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS messages_drafting_queue_idx ON messages (generation_attempts, created_at)
    WHERE generated_at IS NULL AND sent_at IS NULL;
-- Sends whose outcome was lost are reconciled against Gmail (app/send_reconciler.py).
CREATE INDEX IF NOT EXISTS messages_unconfirmed_send_idx ON messages (sent_at)
    WHERE sent_at IS NOT NULL AND sent_message_id IS NULL;
