-- How scanned attachments are read (specs/features/signature-detection.md): 'local' never sends a
-- scan image to Gemini, only the text read on this machine; 'checked' sends the pages a local
-- vision model finds free of signatures, faces and stamps. 'local' is the default for everyone,
-- including users who sent scans to Gemini before: the check misses about 1 in 10 marks.
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS scan_reading TEXT NOT NULL DEFAULT 'local'
  CHECK (scan_reading IN ('local', 'checked'));
