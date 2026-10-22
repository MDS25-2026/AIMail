# Security hardening from the 2026-10-21 review

- **Status:** accepted 2026-10-21 (owner)
- **Owner:** veyroxie
- **Related issue:** epic #138
- **Last updated:** 2026-10-21

## Goal

A white-box review of sign-in, sessions and authorization found no critical or high issues (every
email, document and audit query is scoped to its owner; admin rights come from `app_metadata`), and
four medium and three low ones. Fix all seven.

## Changes

1. **Reply-To (medium).** An approved reply went to the original's whole Reply-To header, so a forged
   `Reply-To: real@corp.example, thief@evil.example` copied it, real details restored, to the thief.
   A Reply-To naming exactly one address is still honoured; one naming several is ignored and the
   reply goes to the sender (`app/gmail_send.py` `_single_address`), as a holding reply already
   refuses. The draft bar now says when a reply goes somewhere other than the sender.
2. **Sign-out (medium).** With the hour-long session cookie expired, sign-out only cleared cookies and
   the week-long refresh token stayed valid. It is now exchanged for one to revoke with, as the admin
   console already did.
3. **Non-ASCII tokens (medium).** `compare_digest` on text raised on non-ASCII and answered 500 before
   authentication; tokens are compared as bytes, so they get 401 (backend) or 403 (agent).
4. **Admin password limit (medium).** Behind the hosting proxy every caller may share one address, so
   five guesses could lock every admin out. The limit is now per address and account.
5. **Log line (low).** `/auth/callback`'s `error` is escaped and capped before it is logged.
6. **GETs that change state (low).** Opening an email marks it read and may start a draft; a cookie
   caller now needs `X-AIMail-Client: 1` there too, which the dashboard and extension always send.
7. **Sign-in calls (low).** `/auth/callback` and `/auth/session/refresh` are limited to 60 a minute
   per caller, generous enough for a booth or office on one address.

## Acceptance criteria

- [ ] Each change has a test that failed before it (`tests/test_security_hardening.py`,
      `tests/test_admin.py`, `lib/__tests__/replyTarget.test.ts`).
- [ ] No new settings; `make check` passes.

## Not changed

Which X-Forwarded-For entry is the real client behind Vercel and Render is still to be read from one
live request; the per-account admin limit removes the lockout either way.
