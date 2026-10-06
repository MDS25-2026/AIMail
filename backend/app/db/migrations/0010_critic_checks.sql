-- The critic computes four concrete checks (grounding, PII, tone, completeness) and, until now,
-- every one was discarded in favour of a self-reported scalar. Store the whole gate result as
-- JSONB rather than a column per check, because the gate design is still moving and a new check
-- should not cost a migration.
--
-- needs_human_review is stored alongside even though it is derivable, so the dashboard can filter
-- on it without unpacking JSON on every row.

ALTER TABLE messages
  ADD COLUMN IF NOT EXISTS critic_checks JSONB,
  ADD COLUMN IF NOT EXISTS needs_human_review BOOLEAN;
