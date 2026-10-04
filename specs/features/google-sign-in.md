# Google sign-in for the dashboard

- **Status:** in-progress
- **Owner:** veyroxie
- **Related:** [ADR 0005](../../docs/adr/0005-dashboard-google-sign-in.md), gap-plan epic #138 (Phase 0)
- **Last updated:** 2026-10-04

## Goal

Remove the API token from the browser. Each person signs in with Google, and sees only the mail of
a mailbox they own.

## Scope

**In scope (stage 1)**
- Backend: `/auth/google/start`, `/auth/callback`, `GET /auth/session`, `POST /auth/session/refresh`,
  `DELETE /auth/session`; `require_auth` accepting the shared token, a Supabase bearer, or the session
  cookie; the CSRF header on cookie requests; mailbox scoping on every email and knowledge route.
- Dashboard: a sign-in page, sign-out, credentialed requests, no token in the bundle, an empty inbox
  for a user with no connected mailbox.

**Out of scope**
- Stage 2, each user's own Gmail (ADR 0005).
- Replacing the admin console's password login.

## Acceptance criteria

- [x] The built dashboard contains no backend token (the token value is in no file under `.output/`).
- [x] With no cookie and no bearer, every route except `/` and the `/auth` sign-in routes answers 401.
- [x] The shared token as a bearer still works, so scripts and tests need no login.
- [x] A valid session cookie works for GET; a POST without `X-AIMail-Client: 1` answers 403.
- [x] A valid Supabase bearer works without the header.
- [x] The mailbox owner sees their mail; another signed-in user gets `[]` from `/emails` and 404 for an id.
- [x] `/auth/google/start` redirects to Supabase with an S256 challenge and sets a Lax verifier cookie.
- [x] `/auth/callback` exchanges the code with that verifier, sets Strict session cookies, clears the
      verifier, and redirects to the dashboard; without a verifier it returns to `/signin` with an error.
- [ ] A real Google sign-in end to end, once the setup below is done (needs the owner's Google and
      Supabase configuration).

## Setup (one time, done by the owner)

1. **Google Cloud console** (project `aimail-505405`): APIs & Services, Credentials, Create
   credentials, OAuth client ID, type "Web application". Authorised redirect URI:
   `https://<your-project-ref>.supabase.co/auth/v1/callback`. Copy the client ID and secret.
2. **OAuth consent screen:** user type External, publishing status Testing, and add each teammate
   under Test users.
3. **Supabase dashboard:** Authentication, Sign In / Providers, Google: enable it and paste the
   client ID and secret.
4. **Supabase dashboard:** Authentication, URL Configuration, Redirect URLs: add
   `http://localhost:8000/auth/callback` (and the deployed backend's URL later).
5. **`.env`:** set `MAILBOX_OWNER_EMAIL` to your Google address, check `BACKEND_PUBLIC_URL` and
   `DASHBOARD_URL`, and delete `VITE_BACKEND_API_TOKEN`.

## Security & privacy notes

- Session tokens live in HttpOnly cookies, never in browser storage (ADR 0004 reasoning).
- The verifier cookie is Lax so it survives the cross-site return from Google; it is single-use
  and expires in ten minutes.
- A user's email comes from the verified Supabase token, never from the request.
