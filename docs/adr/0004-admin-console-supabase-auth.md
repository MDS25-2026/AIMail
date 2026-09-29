# ADR 0004 — Admin console behind Supabase Auth, with tokens held in HttpOnly cookies

- **Status:** Accepted
- **Date opened:** 2026-09-29
- **Date accepted:** 2026-09-29
- **Deciders:** veyroxie (mailbox owner), for review by the team
- **Supersedes:** —

## Context

AImail needs an operator view: is masking healthy, how often does Gemini retry or fall back, why
are drafts sent to review, what did the pipeline do today. The data already exists (`audit_log`,
`messages.critic_checks.model_calls`, review reasons, `masking_status`). What does not exist is a
credential that can gate it.

The dashboard's only credential is `BACKEND_API_TOKEN`, a shared secret that is also compiled into
the browser bundle as `VITE_BACKEND_API_TOKEN`. Anyone who can open the dashboard can read it, so it
cannot distinguish an operator from a reader. `app/core/auth.py` already names per-user Supabase
JWTs as the planned upgrade.

## Decision

**The admin console authenticates real users through Supabase Auth, and a user is an admin only if
`app_metadata.role` is `"admin"`.** The console is a separate FastAPI app mounted at `/admin`, and
the browser never holds a token: the backend exchanges the email and password for a Supabase session
and keeps the tokens in HttpOnly cookies. The rest of the API keeps the shared token for now.

## How it works

- **Sign-in** (`POST /admin/session`): the backend calls Supabase's password grant with the
  project's publishable (anon) key, verifies the returned access token, and refuses anyone without
  the admin role (signing that session out again). On success it sets two cookies:
  `aimail_admin` (access token, `Path=/admin`) and `aimail_admin_refresh` (`Path=/admin/session`),
  both `HttpOnly; Secure; SameSite=Strict`.
- **Every admin request** verifies the access token locally: ES256 signature against the
  project's published JWKS (cached), `aud=authenticated`, the project's issuer, expiry, and the
  role claim. No shared secret is stored on the server.
- **Refresh and sign-out** use the refresh cookie and Supabase's own endpoints; sign-out also
  clears both cookies.
- **CSRF:** `SameSite=Strict` stops cross-site requests carrying the cookies, and every
  state-changing admin call must also send `X-AIMail-Admin: 1`, which a cross-origin form cannot
  set without a CORS preflight the backend refuses.
- **Brute force:** sign-in is rate limited per client (5 per 5 minutes) on top of Supabase's own
  limits.
- **Accounts:** `backend/scripts/admin_accounts.py add|remove|list`, run with the service key.
  `app_metadata` is writable only with the service key; `user_metadata` is user-editable and is
  never consulted.
- **The console is read-only and shows aggregates, ids and masked subjects, never bodies.**

## Rationale

- **Tokens out of JavaScript's reach.** A token in `localStorage` is one XSS away from theft; an
  HttpOnly cookie is not readable by script at all (OWASP HTML5 Security Cheat Sheet; OAuth 2.0 for
  Browser-Based Apps, "backend for frontend" pattern). The dashboard renders untrusted email HTML,
  so this matters here more than usual.
- **No new secret to guard.** Asymmetric JWT verification needs only the public JWKS. The project
  already signs with ES256.
- **The upgrade the code already anticipated.** `auth.py` names Supabase JWTs as the path; this
  takes it for the one surface that cannot wait, without touching every route at once.
- **Real identities.** Every admin action can be attributed to a person, and access is revoked
  per person rather than by rotating a secret everyone shares.

## Alternatives considered

- **A second shared token for admin, entered in the browser.** No new dependency, but still one
  secret shared by every operator, no attribution, and revocation means telling everyone the new
  one. Rejected by the owner in favour of real accounts.
- **supabase-js in the browser.** The standard SPA approach, but it keeps tokens in browser
  storage and adds a frontend dependency. Rejected for the XSS reason above.
- **Replacing the shared token on every route now.** The right end state, but it changes every
  caller (dashboard, scripts, the extension plan) at once, days before submission. Deferred.

## Consequences

- New backend dependency: `PyJWT[crypto]` (MIT; `cryptography` is Apache-2.0/BSD).
- New settings: `SUPABASE_ANON_KEY` (publishable, but kept server-side), `ADMIN_COOKIE_SECURE`.
  `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` already exist for the listener.
- CORS now allows credentials, for the configured and localhost origins only.
- **Operational:** disable public sign-ups in the Supabase dashboard (Authentication, Sign In /
  Providers). A self-registered user cannot become an admin, but there is no reason to accept them.
- The dashboard and backend must share a site (same host, any port) for `SameSite=Strict`
  cookies to flow; true for localhost and for a single deployment host.

## Revisit when

- The rest of the API moves to per-user identity: `require_auth` then verifies the same JWTs, and
  the shared token retires.
- Admin actions become writes (for example re-queueing a quarantined message): add an audit row
  per action with the admin's user id before that ships.
