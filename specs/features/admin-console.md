# Admin console

- **Status:** shipped
- **Owner:** veyroxie
- **Related issue:** user request 2026-09-29 (hackathon's reports page); decision in `docs/adr/0004`
- **Last updated:** 2026-09-29

## Goal

An operator can see, without reading anyone's mail, whether the pipeline is healthy: masking,
quarantine, attachment reading, why drafts go to review, and how reliably Gemini answers.

## Scope

**In scope**
- `/admin` in the dashboard: sign-in form, then the console. Supabase Auth behind the backend;
  tokens in HttpOnly cookies (ADR 0004).
- Panels: mailbox counts; privacy and masking events; review-reason categories (bar list); model
  reliability (attempts, outcomes, fallback use, p50/p95 model time); drafts awaiting review;
  activity log with a failures filter. Window: 1, 7 or 30 days.
- `backend/scripts/admin_accounts.py add|remove|list` to grant access.

**Out of scope**
- Admin actions that change anything (re-queueing, deleting). Read-only by design; ADR 0004 says
  what an action would need first.
- Per-user identity for the rest of the dashboard.

## Acceptance criteria (`backend/tests/test_admin.py`)

- [x] No cookie is 401; the shared dashboard token does not open admin.
- [x] An account without `app_metadata.role = "admin"` is 403, including one claiming the role in
      `user_metadata`; a non-admin sign-in is refused and its session revoked.
- [x] Expired, wrong-audience, wrong-issuer, foreign-key and malformed tokens are 401.
- [x] Sign-in sets `HttpOnly; SameSite=strict` cookies on `/admin` and `/admin/session` and never
      returns a token in the body; sign-out clears both.
- [x] Sign-in without `X-AIMail-Admin` is 403; the sixth try in five minutes is 429; with no anon
      key configured sign-in is 503.
- [x] Review reasons are shown as categories: "does not address: Send the invoice" is counted as
      "does not address".

## Security & privacy notes

Aggregates, ids and already-masked subjects only. Audit details are cut to 240 characters and
contain ids, counts and error reasons, never content.
