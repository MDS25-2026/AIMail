-- Holding reply (specs/features/holding-reply.md): the user's own words, sent automatically when
-- they cannot answer. Opt-in; every condition fails closed.

CREATE TABLE IF NOT EXISTS holding_reply_settings (
  user_id          UUID PRIMARY KEY REFERENCES user_profile(id) ON DELETE CASCADE,
  enabled          BOOLEAN NOT NULL DEFAULT false,
  -- Only emails received after this are ever considered, so switching on never answers a backlog.
  enabled_at       TIMESTAMPTZ,
  active_when      TEXT NOT NULL DEFAULT 'outside_hours' CHECK (active_when IN ('outside_hours', 'leave', 'always')),
  work_days        SMALLINT[] NOT NULL DEFAULT '{1,2,3,4,5}',
  work_start       TIME NOT NULL DEFAULT '09:00',
  work_end         TIME NOT NULL DEFAULT '18:00',
  timezone         TEXT NOT NULL DEFAULT 'Asia/Kuala_Lumpur',
  leave_from       DATE,
  leave_until      DATE,
  audience         TEXT NOT NULL DEFAULT 'correspondents' CHECK (audience IN ('correspondents', 'domain', 'everyone')),
  scope            TEXT NOT NULL DEFAULT 'needs_reply' CHECK (scope IN ('needs_reply', 'all')),
  cooldown_days    SMALLINT NOT NULL DEFAULT 4 CHECK (cooldown_days BETWEEN 1 AND 30),
  templates        JSONB NOT NULL DEFAULT '{}',
  default_language TEXT NOT NULL DEFAULT 'en' CHECK (default_language IN ('en', 'ms', 'zh')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS holding_reply (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES user_profile(id) ON DELETE CASCADE,
  -- One holding reply per email, ever.
  message_id       UUID NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
  recipient_addr   TEXT NOT NULL,
  language         TEXT NOT NULL CHECK (language IN ('en', 'ms', 'zh')),
  scheduled_for    TIMESTAMPTZ NOT NULL,
  sent_at          TIMESTAMPTZ,
  cancelled_reason TEXT,
  sent_message_id  TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS holding_reply_cooldown_idx ON holding_reply (user_id, recipient_addr, sent_at);
CREATE INDEX IF NOT EXISTS holding_reply_due_idx ON holding_reply (scheduled_for) WHERE sent_at IS NULL AND cancelled_reason IS NULL;

-- Set by the listener from List-Id, Precedence, Auto-Submitted, Return-Path and the sender (RFC 3834).
ALTER TABLE messages ADD COLUMN IF NOT EXISTS is_automated BOOLEAN NOT NULL DEFAULT false;

ALTER TABLE holding_reply_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE holding_reply ENABLE ROW LEVEL SECURITY;
