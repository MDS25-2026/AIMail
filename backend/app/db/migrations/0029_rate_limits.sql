-- Rate-limit counters shared by every API instance (app/core/ratelimit.py): one fixed window per key, so
-- N instances enforce one limit instead of N, and a user is limited as themselves, not by proxy IP.
CREATE TABLE IF NOT EXISTS rate_limit_counter (
    key          TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    hits         INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key, window_start)
);
ALTER TABLE rate_limit_counter ENABLE ROW LEVEL SECURITY;
