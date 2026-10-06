-- 0001: RAG policy-grounding tables (document / chunk / embedding).
-- Source of truth for the schema is specs/context/db-schema.md.
-- Dimension 1536 and the cosine HNSW index are pinned in docs/decisions/lane-b-ml.md.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source      TEXT NOT NULL UNIQUE,      -- unique so re-upload replaces, not duplicates
    title       TEXT,
    doc_type    TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunk (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    chunk_idx   INT NOT NULL,
    content     TEXT NOT NULL,
    token_count INT,
    metadata    JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX chunk_document_id_idx ON chunk (document_id);

CREATE TABLE embedding (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id   UUID NOT NULL REFERENCES chunk(id) ON DELETE CASCADE,
    embedding  vector(1536) NOT NULL,      -- gemini-embedding-001, L2-normalized
    model_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX embedding_hnsw_idx ON embedding USING hnsw (embedding vector_cosine_ops);
