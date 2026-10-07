-- Private mode search (specs/features/local-model.md): vectors from the company's local embedding
-- model. Its own table and index, because a local vector and a Gemini vector are not comparable.
CREATE TABLE IF NOT EXISTS local_embedding (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id   UUID NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,
    embedding  vector(768) NOT NULL,       -- embeddinggemma, L2-normalized
    model_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (chunk_id, model_name)
);
CREATE INDEX IF NOT EXISTS local_embedding_hnsw_idx ON local_embedding USING hnsw (embedding vector_cosine_ops);
