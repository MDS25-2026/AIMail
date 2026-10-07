-- Email Auth Status
ALTER TABLE messages ADD COLUMN auth_status TEXT DEFAULT 'pass';

-- Audit Log Cryptographic Hashing
CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE audit_log ADD COLUMN prev_hash TEXT;
ALTER TABLE audit_log ADD COLUMN current_hash TEXT;

-- Create trigger function to securely serialize and hash inserts
CREATE OR REPLACE FUNCTION compute_audit_hash()
RETURNS TRIGGER AS $$
DECLARE
    last_hash TEXT;
BEGIN
    -- Lock table to prevent race conditions during concurrent Go/Python writes
    LOCK TABLE audit_log IN SHARE ROW EXCLUSIVE MODE;

    SELECT current_hash INTO last_hash FROM audit_log ORDER BY created_at DESC, id DESC LIMIT 1;
    IF last_hash IS NULL THEN
        last_hash := '0000000000000000000000000000000000000000000000000000000000000000';
    END IF;

    NEW.prev_hash := last_hash;
    -- Hash: prev_hash + action + detail + success + timestamp
    NEW.current_hash := encode(digest(last_hash || NEW.action || COALESCE(NEW.detail, '') || COALESCE(NEW.success::text, 'false') || extract(epoch from NEW.created_at)::text, 'sha256'), 'hex');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_compute_audit_hash
BEFORE INSERT ON audit_log
FOR EACH ROW
EXECUTE FUNCTION compute_audit_hash();
