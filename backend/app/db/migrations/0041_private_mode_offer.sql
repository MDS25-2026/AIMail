-- 0041_private_mode_offer.sql
-- Private mode is offered once in the inbox (specs/features/local-model.md, #153). This records
-- when the user decided, by switching it either way or choosing "Not now", so it is not asked again.
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS private_mode_decided_at TIMESTAMPTZ;
