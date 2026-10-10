-- 0035_inbox_search_hybrid.sql
-- Lane B & Lane C: Hybrid inbox search and thread Q&A assistant (Issue #144).
-- Adds PostgreSQL tsvector full-text search and pgvector semantic similarity to messages.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS search_vector tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(subject, '') || ' ' || coalesce(body_masked, ''))
  ) STORED;

CREATE INDEX IF NOT EXISTS messages_search_vector_idx ON messages USING gin (search_vector);

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS embedding vector(1536);

CREATE INDEX IF NOT EXISTS messages_embedding_hnsw_idx
  ON messages USING hnsw (embedding vector_cosine_ops);
