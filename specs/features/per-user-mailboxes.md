# Per-user mailboxes: real sign-up, each user sees their own Gmail

- **Status:** draft (owner's decisions recorded 2026-10-04; listener part pending JiaJun's review)
- **Owner:** veyroxie; Lane A (JiaJun) for the listener part
- **Related:** [ADR 0005](../../docs/adr/0005-dashboard-google-sign-in.md) "Stage 2", [google-sign-in.md](./google-sign-in.md), gap-plan epic #138
- **Last updated:** 2026-10-04

## Goal

Anyone signs up with Google, grants Gmail access in the same consent screen, and from then on sees
and replies to their own mailbox, masked exactly as today. Nothing about one user's mail is visible
to another.

## User story

As a new user, I click "Sign in with Google", allow AIMail to read and send my Gmail once, and land
in my own inbox, with drafts written from my mail, so that I never set anything up by hand.

## Scope

**In scope**
- Requesting `gmail.readonly` and `gmail.send` at sign-in, offline, and keeping the Google refresh
  token Supabase returns, encrypted, per user.
- The listener watching every connected mailbox and tagging each stored email with its owner.
- The backend scoping every email route to the signed-in user, and sending from their own account.
- Disconnecting: a user can revoke access, which stops ingest and deletes their token.
- Moving today's rows to the current owner (backfill), and retiring `app/core/mailbox.py`.

**Out of scope**
- Outlook (team-owned; this design leaves room: the connection table has a `provider` column).
- Shared or delegated mailboxes, and teams seeing each other's mail.
- Google's restricted-scope verification itself (an operational step, see below).

## How it works

1. **Sign-in asks for Gmail.** `/auth/google/start` adds the Gmail scopes and asks Google for an
   offline refresh token with a fresh consent (Supabase passes provider options through to Google;
   confirm the exact authorize parameters against Supabase's docs when building). The PKCE exchange
   then returns `provider_token` and `provider_refresh_token` beside the Supabase session.
2. **The refresh token is stored encrypted.** AES-256-GCM with a key in `TOKEN_ENCRYPTION_KEY`
   (Python `cryptography`, already a dependency through PyJWT[crypto]; Go's standard library on the
   listener side, so no new packages). The plaintext token is never logged and never sent to the
   browser.
3. **Google client credentials live server-side.** A refresh token can only be used by the OAuth
   client that issued it, the one configured in Supabase's Google provider, so the backend and
   listener need its ID and secret as `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`.
4. **The listener serves many mailboxes.** It loads every active connection, calls `users.watch`
   for each (same Pub/Sub topic), and routes each notification by its `emailAddress` to that
   mailbox's Gmail client. The history baseline moves from memory to the connection row, so a
   restart resumes each mailbox where it stopped. Every stored row gets `messages.user_id`.
5. **The backend scopes by user.** Every email query filters on `user_id = signed-in user`; a send
   uses that user's token. `Principal` carries the Supabase user id; `has_mailbox` becomes "has an
   active connection".
6. **Disconnect** revokes the token at Google, stops the watch, deletes the connection row, and
   (decision pending, see open questions) deletes or keeps the user's stored mail.

## Data model (new migration; update `specs/context/db-schema.md` first)

**`mailbox_connection`**

| Column | Type | Notes |
|---|---|---|
| `user_id` | `UUID PK` | the Supabase user id (and the matching `user_profile.id`, see finding 1) |
| `provider` | `TEXT NOT NULL` | `gmail` (room for `outlook`) |
| `email` | `TEXT UNIQUE NOT NULL` | the mailbox address Google reported |
| `refresh_token_encrypted` | `BYTEA NOT NULL` | nonce + AES-GCM ciphertext |
| `scopes` | `TEXT[] NOT NULL` | as granted; a missing `gmail.send` disables sending, not reading |
| `history_id` | `BIGINT NULL` | per-mailbox baseline for `history.list` |
| `watch_expires_at` | `TIMESTAMPTZ NULL` | renewed before Gmail's seven-day expiry |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | |

Not exposed through PostgREST to the anon role; the listener reads it with the service key, the
backend through asyncpg. `messages.user_id` (exists since migration 0007) becomes required for new
rows; an index on `(user_id, created_at)` serves the inbox.

## Acceptance criteria

- [ ] A first-time Google user who grants Gmail access lands in their own inbox, with their mail
      ingested and masked, and no setting edited anywhere.
- [ ] User A never sees user B's mail: list, detail, regenerate, refine, translate and send all
      answer as for an unknown id (tested with two users).
- [ ] A reply from user A goes out from A's Gmail account, threaded as today.
- [ ] The refresh token is stored only encrypted; no log line, API response or browser storage
      contains it (grep the logs of a full sign-up and send).
- [ ] Restarting the listener resumes every mailbox from its stored baseline without re-ingesting.
- [ ] Disconnecting revokes the token at Google and stops new mail for that user within one poll.
- [ ] Today's rows belong to the current owner after the backfill; `app/core/mailbox.py` is gone.

## Operational setup

- Google Cloud: add the Gmail read and send scopes to the OAuth consent screen. While the app is in
  "Testing", only listed test users (up to 100) can grant them, and they see Google's "unverified
  app" warning. Fine for the FYP and the booth.
- Public launch needs Google's verification for restricted scopes, including a third-party security
  assessment, or a Workspace-internal app for a single company. Weeks, not days.
- `.env`: `TOKEN_ENCRYPTION_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` (server
  side only; never `VITE_`).

## Security & privacy notes

- Masking is unchanged and per message, so every user gets the same protection.
- The refresh token is the most sensitive thing AIMail holds: encrypted at rest, decrypted only in
  memory to mint access tokens, never logged. Key rotation re-encrypts rows (a script).
- PDPA: the token is collected for one purpose (reading and replying to the user's mail) and
  deleted on disconnect; retention of stored mail after disconnect is an explicit decision below.

## Open questions

- ~~On disconnect, delete the user's stored mail?~~ **Decided 2026-10-04: yes.** Three distinct
  actions:
  - **Sign out** ends the session only. Ingest continues, so the inbox is ready next time; nothing
    is deleted.
  - **Disconnect Gmail** stops ingest, revokes and deletes the stored Gmail token, and deletes the
    user's stored masked mail, drafts and summaries. The account and settings stay; they can
    reconnect.
  - **Delete account** does all of that and removes the account, settings, knowledge base and
    writing profile (the PDPA right to erasure).
- ~~Does each user get their own knowledge base, or is it shared per company?~~ **Decided
  2026-10-04:** per user now; enterprise accounts later share one per company (ADR 0005).
- ~~The admin console with many users~~ **Decided 2026-10-04:** aggregates only. The flagged-drafts
  list becomes counts by reason; no individual subject or id from any mailbox.

## Audit findings that change the design (2026-10-04)

A code audit of every single-mailbox assumption found these, each checked in code:

1. **`messages.user_id` references `user_profile(id)`, not `auth.users`** (migration 0007), and the
   backend ORM `Message` has no `user_id` at all. **Decided 2026-10-04:** every Supabase user gets a
   `user_profile` row with `id` = their auth user id, so the existing key and the personalisation
   tables keep working; the ORM gains `user_id`.
2. **`UNIQUE (gmail_message_id)` is global** (migration 0003), and the listener's "already stored?"
   check and insert conflict key use it alone. Gmail ids are per mailbox, so a collision would
   silently drop another user's email. Becomes `UNIQUE (user_id, gmail_message_id)`.
3. **`document.source` is globally unique** (migration 0001), so one user uploading `policy.pdf`
   would replace another's. Documents get `user_id`, uniqueness `(user_id, source)`, and retrieval
   filters by owner (otherwise drafts could be grounded on, and cite, another user's documents).
4. **The listener's Pub/Sub client authenticates as the mailbox user** (pubsub OAuth scope). End
   users cannot hold project permissions, so the subscriber moves to a service account; per-user
   tokens are used only for Gmail.
5. **The admin console's flagged-drafts list shows individual masked subjects** from every mailbox.
   With many users that breaks "aggregates only": drop the subject or aggregate it.
6. **Every message query loads by id alone** (detail, regenerate, refine, translate, send, claim,
   mark-read) and the thread lookup by `thread_id` alone; all add `user_id`.
7. **Throughput is global:** the draft poller (2 per cycle), the quarantine loop (one batch of 20)
   and the rate limiter (per IP, in memory) let one busy mailbox starve the rest; all become fair
   per user. A revoked token must not crash the listener (`setupWatch` calls `log.Fatalf` today).
8. **The sign-in copy changes:** "Google only confirms who you are" stops being true once AIMail
   reads Gmail, and "ask the mailbox owner" becomes a "Connect Gmail" button.

## Implementation order (each step mergeable)

1. ~~Migration and `mailbox_connection`, encryption helpers in Python and Go, with tests.~~ Done
   2026-10-05: migration 0016 (applied), `app/core/token_crypt.py`, `listener/tokencrypt.go`, one
   shared test vector both suites decrypt.
2. ~~Sign-in requests the scopes and stores the connection.~~ Done 2026-10-05: `/auth/google/start`
   asks for Gmail read and send, offline, with consent; the callback checks the granted scopes with
   Google's tokeninfo and stores the sealed connection (`app/connections.py`); failures are logged
   and never block sign-in. Verified against Supabase with a throwaway row.
3. Backend scoping by `user_id`, and sending with the user's token. Scoping done 2026-10-05:
   `app/core/ownership.py` (one `Scope` used by every email and document query), migration 0017,
   and the original mailbox's rows hand over to its account when it connects. Sending done the
   same day: each reply uses the owner's own sealed token, refreshed with the Google web client
   (`GOOGLE_OAUTH_CLIENT_ID/SECRET`), cached per mailbox; a read-only grant answers `403
   send_not_granted` before anything is claimed. Rows with no owner still send via `token.json`.
4. ~~Listener multi-mailbox ingest with per-mailbox baselines (Lane A).~~ Done 2026-10-05, for
   JiaJun's review: `listener/mailboxes.go` loads every connection, watches each on the shared
   topic, routes notifications by address (unknown ones acked and dropped), seeds a first-time
   inbox with its newest 10 emails, saves each baseline and watch expiry on the connection row,
   and picks up new sign-ups every two minutes. A failing mailbox is logged and retried, never
   fatal. Rows carry `user_id`; duplicates are judged per mailbox (`on_conflict=user_id,gmail_message_id`).
   Interim: Pub/Sub still authenticates as the `token.json` account (finding 4).
5. Backfill, delete `app/core/mailbox.py`, disconnect flow and its UI.
