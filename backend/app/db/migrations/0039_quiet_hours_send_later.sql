-- Quiet hours, send later and snooze (specs/features/quiet-hours-send-later.md).

-- The sender's UTC offset from their Date header, in minutes (+480 for +0800); NULL when unparseable.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS sender_utc_offset_minutes SMALLINT;
-- Hidden from the inbox until then.
ALTER TABLE messages ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMPTZ;

-- The row with no user is the company default; a user's own row replaces it for them.
CREATE TABLE IF NOT EXISTS quiet_hours (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID REFERENCES user_profile(id) ON DELETE CASCADE,
  starts       TIME NOT NULL DEFAULT '21:00',
  ends         TIME NOT NULL DEFAULT '08:00',
  -- ISO weekdays, 1 = Monday: Kelantan, Terengganu and Kedah rest Friday and Saturday (5, 6).
  weekend_days SMALLINT[] NOT NULL DEFAULT '{6,7}',
  timezone     TEXT NOT NULL DEFAULT 'Asia/Kuala_Lumpur',
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (starts <> ends)
);
CREATE UNIQUE INDEX IF NOT EXISTS quiet_hours_user_idx ON quiet_hours (user_id) NULLS NOT DISTINCT;
INSERT INTO quiet_hours (user_id) SELECT NULL WHERE NOT EXISTS (SELECT 1 FROM quiet_hours WHERE user_id IS NULL);

CREATE TABLE IF NOT EXISTS scheduled_send (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id       UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  -- NULL for the original mailbox's unowned rows, like messages.user_id.
  user_id          UUID REFERENCES user_profile(id) ON DELETE CASCADE,
  -- Known details as placeholders, as an approved reply is stored.
  draft            TEXT NOT NULL,
  send_at          TIMESTAMPTZ NOT NULL,
  sent_at          TIMESTAMPTZ,
  cancelled_reason TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- One waiting send per email; scheduling again replaces it.
CREATE UNIQUE INDEX IF NOT EXISTS scheduled_send_pending_idx ON scheduled_send (message_id)
  WHERE sent_at IS NULL AND cancelled_reason IS NULL;
CREATE INDEX IF NOT EXISTS scheduled_send_due_idx ON scheduled_send (send_at)
  WHERE sent_at IS NULL AND cancelled_reason IS NULL;

ALTER TABLE quiet_hours ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_send ENABLE ROW LEVEL SECURITY;
