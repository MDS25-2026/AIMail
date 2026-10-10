-- Lists ordered by arrival with no owner filter (the bearer-token scripts, EVERYTHING scope, and the
-- original mailbox's unowned rows): messages_user_created_idx (0017) leads with user_id and cannot
-- serve them.
CREATE INDEX IF NOT EXISTS messages_created_idx ON messages (created_at DESC, id DESC);
