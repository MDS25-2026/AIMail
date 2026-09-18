-- How many refine rounds the critic forced before the draft passed. The refine loop runs while
-- confidence is under the threshold, so the stored confidence is always a post-repair value: a
-- draft rescued by three rewrites is today indistinguishable from one that passed first time.
-- This column is the only observable evidence that the review gate ever engages.
--
-- Nullable: rows generated before it existed have no attempt history, and NULL says "unknown"
-- rather than falsely claiming a clean first pass.

ALTER TABLE messages ADD COLUMN IF NOT EXISTS critic_attempts SMALLINT;
