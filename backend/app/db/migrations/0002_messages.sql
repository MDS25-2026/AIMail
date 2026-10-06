-- 0002: ingestion tables. Lane A (JiaJun's Go listener) inserts into `messages` + `audit_log`
-- via the Supabase PostgREST API; the Lane-A column names match his StoredMessage / AuditLogEntry
-- Go structs exactly. Lane B writes the nullable priority columns later.
-- See specs/context/db-schema.md.

CREATE TABLE messages (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gmail_message_id         TEXT,
    from_addr                TEXT,
    subject                  TEXT,
    body_masked              TEXT,       -- Seam 1: what Lane B reads
    snippet_masked           TEXT,
    emails_masked            INT,
    phones_masked            INT,
    received_at              TIMESTAMPTZ,
    importance               SMALLINT,   -- Lane B: 0/1/2 = LOW/MEDIUM/HIGH (null until scored)
    importance_confidence    REAL,
    deadline_at              TIMESTAMPTZ,
    importance_model_version TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action     TEXT,
    detail     TEXT,
    success    BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
