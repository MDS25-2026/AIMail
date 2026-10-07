-- Sender verification and the audit hash chain (specs/features/sender-verification-and-audit.md).
-- Replaces PR #161's 0019/0020, which some databases already ran: every statement is safe to repeat.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS auth_status TEXT DEFAULT 'pass';

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES user_profile(id) ON DELETE SET NULL;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS prev_hash TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS current_hash TEXT;
-- The chain's order, assigned under the lock; created_at cannot order it (rows in one transaction share it).
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS chain_seq BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS audit_log_chain_seq_idx ON audit_log (chain_seq);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log (user_id);

-- One formula, used by the trigger and by verification. chr(31) separates fields so "ab"+"c" is not "a"+"bc".
CREATE OR REPLACE FUNCTION audit_row_hash(prev_hash TEXT, chain_seq BIGINT, action TEXT, detail TEXT,
                                          success BOOLEAN, user_id UUID, created_at TIMESTAMPTZ)
RETURNS TEXT
LANGUAGE sql IMMUTABLE
SET search_path = public, extensions
AS $$
    SELECT encode(digest(concat_ws(chr(31), prev_hash, chain_seq::text, COALESCE(action, ''),
                                   COALESCE(detail, ''), COALESCE(success::text, ''),
                                   COALESCE(user_id::text, ''), extract(epoch FROM created_at)::text),
                         'sha256'), 'hex')
$$;

CREATE OR REPLACE FUNCTION compute_audit_hash()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, extensions
AS $$
DECLARE
    last_seq BIGINT;
    last_hash TEXT;
BEGIN
    -- An advisory lock, not LOCK TABLE: the INSERT already holds ROW EXCLUSIVE, so two writers each
    -- asking for SHARE ROW EXCLUSIVE deadlocked and one audit row was lost.
    PERFORM pg_advisory_xact_lock(hashtext('audit_log_chain'));
    SELECT a.chain_seq, a.current_hash INTO last_seq, last_hash
    FROM audit_log a WHERE a.chain_seq IS NOT NULL ORDER BY a.chain_seq DESC LIMIT 1;
    NEW.chain_seq := COALESCE(last_seq, 0) + 1;
    NEW.prev_hash := COALESCE(last_hash, repeat('0', 64));
    NEW.current_hash := audit_row_hash(NEW.prev_hash, NEW.chain_seq, NEW.action, NEW.detail,
                                       NEW.success, NEW.user_id, NEW.created_at);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_compute_audit_hash ON audit_log;
CREATE TRIGGER trg_compute_audit_hash
BEFORE INSERT ON audit_log
FOR EACH ROW
EXECUTE FUNCTION compute_audit_hash();
