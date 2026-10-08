-- Integrity fixes from the 2026-10-08 audit (specs/context/backbone-contracts.md).

-- Every public table is reachable through PostgREST; 0023 missed this one.
ALTER TABLE local_embedding ENABLE ROW LEVEL SECURITY;

-- Two embedding passes at once could store the same vector twice and retrieval returned duplicates.
DELETE FROM embedding a USING embedding b
WHERE a.chunk_id = b.chunk_id AND a.model_name = b.model_name AND a.ctid > b.ctid;
CREATE UNIQUE INDEX IF NOT EXISTS embedding_chunk_model_idx ON embedding (chunk_id, model_name);

-- The hash covers user_id; ON DELETE SET NULL rewrote it on account deletion and broke the chain, and the
-- deletion's own audit row was refused. The id stays, opaque, once the profile is gone.
ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_user_id_fkey;

-- A ledger is append-only: nothing, not even the service role, edits or removes a row.
CREATE OR REPLACE FUNCTION refuse_audit_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END;
$$;
DROP TRIGGER IF EXISTS trg_audit_append_only ON audit_log;
CREATE TRIGGER trg_audit_append_only
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW
EXECUTE FUNCTION refuse_audit_change();

-- Unknown is unverified, never pass: a write path that forgets the verdict fails closed.
ALTER TABLE messages ALTER COLUMN auth_status SET DEFAULT 'unverified';
UPDATE messages SET auth_status = 'unverified' WHERE auth_status IS NULL;
ALTER TABLE messages ALTER COLUMN auth_status SET NOT NULL;
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_auth_status_check;
ALTER TABLE messages ADD CONSTRAINT messages_auth_status_check
    CHECK (auth_status IN ('pass', 'spoof_detected', 'unverified', 'sender_confirmed'));
