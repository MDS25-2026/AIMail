-- 0042_follow_up.sql
-- Follow-ups from the To-do page (specs/features/todo-page.md): set when a follow-up to this sent
-- reply is claimed for sending, so two clicks or two tabs cannot send it twice.
ALTER TABLE sent_message ADD COLUMN IF NOT EXISTS followed_up_at TIMESTAMPTZ;
