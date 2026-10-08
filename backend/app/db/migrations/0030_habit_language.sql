-- Learned writing habits are kept per language (app/writing_style.py, learn): a Malay greeting is not
-- an English one. NULL marks a habit learned before this column; it applies to every language until
-- the next relearn replaces it, and a hidden habit stays hidden whatever its language.
ALTER TABLE style_habit ADD COLUMN IF NOT EXISTS language TEXT;
ALTER TABLE style_habit DROP CONSTRAINT IF EXISTS style_habit_language_known;
ALTER TABLE style_habit ADD CONSTRAINT style_habit_language_known
    CHECK (language IS NULL OR language IN ('en', 'ms', 'zh'));
