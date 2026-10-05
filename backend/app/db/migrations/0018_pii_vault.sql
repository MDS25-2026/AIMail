-- Restorable masking (specs/features/restorable-masking.md, ADR 0006): each email's personal details,
-- placeholder to value, sealed with PII_VAULT_KEY by the listener and bound to the owner and Gmail id.
-- NULL for emails stored before this, quarantined emails, and once the retention job empties it.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS pii_vault BYTEA;
