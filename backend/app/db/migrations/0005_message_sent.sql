-- Record when an approved reply was sent, so the dashboard reflects it and we don't send twice.

ALTER TABLE messages ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ;
