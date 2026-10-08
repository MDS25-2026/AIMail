-- 6-category B2B email taxonomy classifier (specs/features/category-classifier.md, #141).
-- Persists the model's predicted functional category and calibrated confidence.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS category TEXT NULL;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS category_confidence REAL NULL;

CREATE INDEX IF NOT EXISTS messages_category_idx ON messages (category);
