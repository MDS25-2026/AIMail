-- Add user_id to audit_log for per-user compliance tracking (#148 / PDPA)
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES user_profile(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);

-- Update cryptographic hashing trigger to incorporate user_id into the SHA-256 digest
CREATE OR REPLACE FUNCTION compute_audit_hash()
RETURNS TRIGGER AS $$
DECLARE
    last_hash TEXT;
BEGIN
    LOCK TABLE audit_log IN SHARE ROW EXCLUSIVE MODE;

    SELECT current_hash INTO last_hash FROM audit_log ORDER BY created_at DESC, id DESC LIMIT 1;
    IF last_hash IS NULL THEN
        last_hash := '0000000000000000000000000000000000000000000000000000000000000000';
    END IF;

    NEW.prev_hash := last_hash;
    -- Digest: prev_hash + action + detail + success + user_id + timestamp
    NEW.current_hash := encode(digest(last_hash || COALESCE(NEW.action, '') || COALESCE(NEW.detail, '') || COALESCE(NEW.success::text, 'false') || COALESCE(NEW.user_id::text, '') || extract(epoch from NEW.created_at)::text, 'sha256'), 'hex');

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
