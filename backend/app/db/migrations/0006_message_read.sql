-- Record when a message was first opened, so the inbox can distinguish read from unread.
-- Nullable: every existing row is treated as unread, which is the safe default — better to
-- show something as needing attention than to hide it.

ALTER TABLE messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ;
