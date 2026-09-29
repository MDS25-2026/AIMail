# Request tracing and HTTP hardening

- **Status:** shipped
- **Owner:** veyroxie
- **Related issue:** hackathon-reuse review, item D and the middleware findings
- **Last updated:** 2026-09-29

## Goal

Every log line can be traced to the request that caused it, across the backend and the agent,
without any line holding email content. Model-spending routes cannot be used to drain the
Gemini quota, and no response can be cached, framed or sniffed.

## Scope

**In scope**
- One root log handler (`app/core/logging_setup.py`) with the request id on every line, noisy
  libraries held at WARNING, `LOG_LEVEL` with a safe fallback. Used by the backend and the agent.
- A middleware (`app/core/middleware.py`) that sets the id, echoes it, forwards it to Lane C,
  logs one timing line per request (path only, no query string) and sets security headers.
- `RateLimiter` generalised from the ingestion limiter, with idle-client eviction, applied to
  the four model-spending routes.
- `hide_parameters=True` on the SQLAlchemy engine, so a logged DB error never carries bound
  values (email bodies).

**Out of scope**
- `GET /emails/{id}` is not rate limited: it generates only on first open, and limiting it
  would throttle ordinary browsing.
- Proxy-aware client identity (`X-Forwarded-For`): single host, no proxy.

## Acceptance criteria

- [x] Every response, including a 401, carries `X-Request-ID`, `Cache-Control: no-store` and
      the security headers (`tests/test_middleware.py`).
- [x] An incoming id with a newline, markup or over 64 chars is replaced, never logged as sent.
- [x] The eleventh model-spending request in a minute from one client gets 429.
- [x] An idle client's window is evicted.

## Security & privacy notes

Log lines hold method, path, status and duration, model names and status codes. Never bodies,
drafts, queries or bound SQL parameters.
