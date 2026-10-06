-- Expired Google access (specs/features/per-user-mailboxes.md): Google refused the stored refresh
-- token (Testing-mode tokens expire after 7 days). Set by the listener or the send path, cleared
-- by signing in again.
ALTER TABLE mailbox_connection ADD COLUMN IF NOT EXISTS needs_reconnect BOOLEAN NOT NULL DEFAULT false;
