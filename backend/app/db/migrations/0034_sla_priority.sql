-- 0015_sla_priority.sql
-- Lane A: Deterministic SLA priority classification floor.
-- Stored at ingestion time by the Go listener (ClassifySLA).
-- Values: CRITICAL, HIGH, MEDIUM, LOW, or NULL (unset, let AI decide).

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS sla_priority TEXT;

CREATE INDEX IF NOT EXISTS messages_sla_priority_idx ON messages (sla_priority);
