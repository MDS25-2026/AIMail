-- The policy chunks a draft was grounded on, captured when it was generated. Stored rather than
-- re-retrieved at read time: the knowledge base changes, and the reviewer needs to see what the
-- model actually saw, not what a search would return today. Chunks are policy text, never mail.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS rag_sources JSONB;
