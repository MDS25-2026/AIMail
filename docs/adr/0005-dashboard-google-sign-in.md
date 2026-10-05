# ADR 0005 — Dashboard sign-in with Google through Supabase, scoped to the user's own mailbox

- **Status:** Accepted
- **Date opened:** 2026-10-04
- **Date accepted:** 2026-10-04
- **Deciders:** veyroxie (mailbox owner)
- **Supersedes:** the shared-token part of `app/core/auth.py`; extends ADR 0004

## Context

Every dashboard request carried `BACKEND_API_TOKEN`, compiled into the browser bundle as
`VITE_BACKEND_API_TOKEN`. Anyone who could load the dashboard could read it and call every route,
including sending email. The 30 Sep audit made this a Phase 0 item, and meeting 30 raised it again.
The team plans Google sign-in for users and an Outlook add-in later, and the owner asked that each
user see only their own mailbox.

## Decision

**Users sign in with Google through Supabase Auth, the backend holds the session in HttpOnly
cookies, and every route checks who is signed in and whose mailbox they may see.** The shared token
stays, server-side only, for scripts and tests; it is never in the browser again.

## How it works

- **Sign-in** uses Supabase's OAuth with PKCE, run by the backend:
  `GET /auth/google/start` makes a code verifier, keeps it in a short-lived HttpOnly cookie, and
  redirects to Supabase's `/authorize?provider=google`. Google sends the user back through Supabase
  to `GET /auth/callback?code=…`, where the backend exchanges the code and verifier for a session
  and sets the cookies, then redirects to the dashboard.
- **The verifier cookie is `SameSite=Lax`**, because the callback arrives as a cross-site redirect
  and browsers drop `Strict` cookies on it. It lives ten minutes, on path `/auth`, and is cleared on
  use. The session cookies are `Strict`, like the admin console's.
- **Every request** is authenticated by `require_auth`, in this order: the shared token as a bearer
  (scripts, tests); a Supabase access token as a bearer (the Chrome extension and Outlook add-in,
  which cannot rely on the dashboard's cookies); the session cookie (the dashboard). Tokens are
  verified locally against the project's ES256 keys, the same check the admin console uses.
- **CSRF:** a cookie-authenticated request that changes state must send `X-AIMail-Client: 1`. A
  form cannot send it, and a cross-origin script cannot without a preflight, which only the
  dashboard origins pass (`app/core/cors.py`). Bearer requests need no header: a browser never
  attaches one by itself.
- **Mailbox scope (stage 1):** the listener ingests one mailbox. At startup the backend asks Gmail
  which address its own login belongs to (`app/core/mailbox.py`); a signed-in user whose verified
  email matches it sees and acts on its mail, anyone else sees an empty inbox and gets 404 for any
  email id. `MAILBOX_OWNER_EMAIL` is only a fallback if Gmail cannot be reached. Scripts using the
  shared token see everything.

## Stage 2: each user's own Gmail

Not built here. Each user's knowledge base (uploaded company documents) belongs to that user in
stage 2; enterprise accounts later share one knowledge base per company (decided by the mailbox
owner, 2026-10-04). The same Google consent requests `gmail.readonly` and `gmail.send`; Supabase hands
back the provider refresh token, which the backend stores encrypted per user; the listener watches
every connected mailbox and tags each row with `messages.user_id` (the column exists since
migration 0007); sends use the owner's token; and the scope check becomes `user_id = signed-in
user`. Until Google verifies the app for restricted scopes, up to 100 listed test users can connect.

## Rationale

- **No secret in the browser.** The bug was a credential anyone could copy; a session cookie is
  per person, revocable, and unreadable by script.
- **Established pieces only.** Supabase's documented PKCE flow and the backend-for-frontend cookie
  pattern already used for the admin console (ADR 0004); no new crypto, no new library.
- **One check, several clients.** Cookie for the dashboard, bearer for the extension and add-in,
  both verified by the same function, so stage 2 changes one place.

## Alternatives considered

- **A server-side proxy holding the shared token.** Hides the token, but anyone who can open the
  dashboard can still use the proxy: it moves the hole rather than closing it.
- **supabase-js in the browser.** The usual SPA approach, but it keeps tokens in browser storage,
  and the dashboard renders untrusted email HTML (ADR 0004's reasoning).
- **An email allowlist.** Simple, but the owner asked for per-mailbox access, which the stage 1
  scope expresses directly and stage 2 generalises.

## Consequences

- New settings: `BACKEND_PUBLIC_URL` (where Supabase sends the user back) and `DASHBOARD_URL`
  (where the backend sends them next). The mailbox owner needs no setting (read from Gmail).
- `VITE_BACKEND_API_TOKEN` is gone from the dashboard; remove it from `.env`.
- **Operational:** a Google OAuth client, the Google provider enabled in Supabase, and the backend
  callback in Supabase's allowed redirect URLs. Steps in `specs/features/google-sign-in.md`.
- **Deployment:** cookies need the dashboard and backend on one site (for example
  `app.example.com` and `api.example.com`, or a Vercel rewrite from the dashboard to the backend).
  Two unrelated domains would make the cookies third-party, and browsers block those.

## Revisit when

- Stage 2 lands: the scope check moves from the one Gmail owner to `messages.user_id`.
- Admin becomes a role on the same sign-in rather than a separate password login.
