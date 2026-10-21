# Live inbox: new mail and finished drafts arrive without a reload

- **Status:** in-progress (slice 1: the messages table; the Vercel keepalive check is recorded under "As built" once the preview is up)
- **Owner:** HyperByte12263 (Han, Lane D) for the dashboard; veyroxie (Lane B) for the stream
- **Related issue:** #138 (gap-plan epic)
- **Last updated:** 2026-10-19

## Goal

The inbox list refetches only on window focus, after a mutation, or on reload, and the open email
polls every 3 s for its draft. New mail sits in Supabase for minutes before the dashboard shows it.
A new email, a finished draft, a category or language change, and a send or snooze from another tab
should show within about a second, with no reload and no polling.

## User story

As someone working through my inbox, I want new emails and their drafts to appear as they arrive,
so that I can leave the dashboard open and trust it instead of reloading to check.

## Scope

**In scope**
- Postgres announces every change to `messages` a dashboard shows (`notify_mailbox_change`,
  migration 0046): ids and a kind only (`new`, `draft`, `state`), never content.
- The backend holds one LISTEN connection while at least one dashboard is connected, and fans each
  notice out to that owner's open streams (`backend/app/events.py`).
- `GET /events`: server-sent events for the caller's own mailbox, cookie-authenticated through the
  same `/api` rewrite as everything else. A `retry` hint, then `mailbox` events, with a comment line
  every 25 s while quiet.
- The dashboard opens one stream per tab (`useMailboxEvents`, mounted once at the root by
  `LiveInboxProvider`, so moving between pages keeps it open; only on the pages inside `AppShell`), treats
  each event as a hint to refetch the inbox and the To-do (coalesced to one refetch per 500 ms), and
  refreshes the open email when its draft lands. A small Live / Reconnecting status in the header.
- Three drops in a row and the inbox polls every 60 s until the stream is back. Every (re)open
  refetches once, so nothing missed while disconnected stays missed.
- Not in the demo (no backend) and not while signed out.

**Out of scope**
- `sent_messages` and `scheduled_sends` events (You replied, Sent list): slice 2, same trigger
  function.
- Removing the draft poll in `useEmail` altogether: while the stream is live it already runs at
  30 s instead of 3 s (see Decisions); it stays as the bounded safety net.
- Browser or OS notifications; the Chrome extension panel (it can use the same hook later).
- Supabase Realtime: the browser would need the anon key and RLS, a second trust surface, and it is
  the one option that needs a paid Supabase plan.

## Acceptance criteria

- [ ] Given the dashboard is open on Primary, when the listener stores a new email for me, then it
      is in the list within 2 s with no reload, and the Updates count changes if it is automated.
- [ ] Given the open email is drafting, when the worker stores the draft, then the editor fills
      within 2 s.
- [ ] Given two tabs, when I send or snooze in one, then the other shows it within 2 s.
- [ ] Given a Render deploy mid-session, then the stream reconnects by itself, the inbox refetches
      once, and no error is shown.
- [ ] Given users A and B both connected, then an event for A's email never reaches B (backend
      test: the fan-out is keyed by the signed-in principal, never by anything the client sends).
- [ ] Given the NOTIFY payload, then it carries `user_id`, `message_id` and `kind` only; a payload
      of any other shape is dropped (backend test).
- [ ] Given four streams from one user, then the fourth is refused with the standard error envelope
      (429) and the first three keep working.
- [ ] Given the backend's LISTEN connection drops, then it is back within 10 s and every connected
      tab received `resync`.
- [ ] Given demo mode or a signed-out page, then no stream is opened.
- [ ] Given the Vercel preview URL, when a stream is left open for 10 minutes, then it is still
      open (manual check, recorded under "As built").
- [ ] Strings in `en`, `ms` and `zh`; colours are palette tokens only.

## API surface

`GET /events` (not in the generated types: the body is an event stream, not JSON). Documented in
[`../context/api-contracts.md`](../context/api-contracts.md).

```
retry: 3000

id: 1
event: mailbox
data: {"kind": "new", "messageId": "5f0c9a2e-..."}

: ping
```

`kind` is `new` (inserted), `draft` (the draft changed), `state` (anything else the dashboard shows:
read, sent, snoozed, dismissed, category, language, sender check, masking), or `resync` (the
listener reopened: refetch). Headers: `Cache-Control: no-store`, `CDN-Cache-Control: no-store`
(Vercel honours upstream cache headers on rewrites; a cached event stream must never happen),
`X-Accel-Buffering: no`. 404 for the service token (no mailbox), 429 past three streams per user.

## Data model

No table or column. Migration 0046 adds `notify_mailbox_change()` and the trigger
`trg_notify_mailbox_change` on `messages` (`AFTER INSERT OR UPDATE OF draft_reply, ai_summary,
category, language, read_at, sent_at, snoozed_until, dismissed_at, auth_status, masking_status`).
Recorded in [`../context/db-schema.md`](../context/db-schema.md).

## Dependencies

- The session pooler on port 5432 (what `DATABASE_URL` already is): session mode keeps
  LISTEN/NOTIFY; transaction mode on 6543 does not. One more pooled connection while anyone is
  connected, none when idle. Free plan is enough.
- Vercel's rewrite to an external origin: a proxied response may stay open as long as the origin
  sends a byte at least every 120 s (the 25 s ping). The Nitro proxy rule is emitted as a CDN
  rewrite, not a function, so function duration limits do not apply.
- Render: no fixed idle timeout on a web-service response, 100 min total; streams close on deploy
  and the browser's EventSource reconnects after the `retry` hint.

## Edge cases & failure modes

- **Listener drops (pooler maintenance):** reconnect every 5 s with a WARNING per loss; every
  reopen broadcasts `resync`.
- **Burst (a catch-up of 200 emails):** the client refetches at most once per 500 ms; a tab that
  stops reading gets its queue replaced by one `resync` instead of a backlog.
- **Vercel's 120 s rule:** the ping every 25 s leaves a 4x margin; if the CDN still cuts the
  stream, EventSource reconnects and the open refetches.
- **Draft event while the reader marked the email unread:** the open email's query refetches with
  its own `keepUnread` flag, so it is not marked read again.
- **A row with no owner (the retired mailbox):** `user_id` is null, the notice is dropped.
- **A stolen stream** reveals timing and ids only, never content.
- **Deploy or restart:** uvicorn drains open requests before stopping, and a stream never ends on
  its own. `app/combined.py` ends every stream the moment uvicorn is told to exit, so the worker's
  own clean stop still runs; the API-only image caps the drain at 20 s. The browser reconnects to
  the new instance after the `retry` hint.

## Security & privacy notes

- The payload is ids only; the trigger never reads a content column. NOTIFY payloads are visible
  to any session listening on the channel and may appear in logs, which is why.
- The stream is scoped to `request.state.principal.user_id`, set by `require_auth`; the client
  sends nothing that selects a mailbox. The service token gets no stream.
- Nothing is stored; no new environment variable.

## Open questions

- Whether Supavisor's session mode delivers notifications through a long idle period without a
  heartbeat on the LISTEN connection itself; the first week on the preview tells.

## Implementation notes

- `backend/app/events.py`: `MailboxEvents` (per-user `asyncio.Queue`s, lazy LISTEN task),
  `event_lines` (the body), `parse_notice`. `GET /events` in `app/main.py`; `events.close()` in the
  lifespan. The API still starts no background task on its own: the listener starts with the first
  stream and stops with the last.
- `src/lib/queries/events.ts`: `useMailboxEvents` (the only file that may import React Query
  outside `src/lib/queries`), exported through `src/lib/queries/index.ts`. `LiveInboxProvider`
  (`src/components/`) mounts it once in `__root.tsx` for the paths in `src/lib/liveInbox.ts` (the
  pages inside `AppShell`; a test keeps the two in step) and shares the state through
  `LiveInboxContext`; `AppShell` reads it with `useLiveState` and shows `LiveStatus`.
- `src/lib/queries/inboxRefresh.ts`: a burst of `draft` and `state` events refetches page 1 alone
  and swaps it in, when more than one page is loaded, none of the emails is on a later page, and
  the fresh page 1 still ends on the same row (its `nextCursor` is unchanged). Otherwise the whole
  list is invalidated, as it always is for `new` (with older pages loaded, page 1 is full, so a new
  row always moves its edge), `resync`, every (re)open and the fallback poll.
- Tests: `backend/tests/test_events.py`, `src/lib/__tests__/inboxRefresh.test.tsx`, `src/lib/__tests__/useMailboxEvents.test.tsx`,
  `src/lib/__tests__/liveInbox.test.ts`.

## Decisions

- 2026-10-19: SSE from the backend, fed by a Postgres trigger. Rationale: one-way, plain HTTP,
  reconnects natively, passes the Vercel rewrite; the trigger is the one place the listener's
  PostgREST writes and the worker's SQLAlchemy writes both pass. Alternatives: a 30 s poll (a
  baseline request per user forever and still a delay), WebSockets (nothing goes browser to server
  on this channel), Supabase Realtime (anon key and RLS in the browser, paid plan).
- 2026-10-21: while the stream is live, the open email's draft poll runs every 30 s, not 3 s
  (`LIVE_DRAFT_POLL_MS`); reconnecting, off, or in the extension it stays at 3 s. Rationale: a
  finished draft arrives as a `draft` event, but a failed attempt only bumps `generation_attempts`,
  which the trigger does not watch, so "Drafting" would never end without a poll. Alternatives:
  no poll when live (stuck on a failure), adding `generation_attempts` to the trigger (a backend
  migration for one client concern).
- 2026-10-21: the stream moved from `AppShell` to the root. Rationale: every route renders its own
  `AppShell`, so each page change closed the stream and the reopen refetched the whole inbox.
  Alternatives: a pathless layout route (moves every route file), a ref-counted module-level
  stream (a grace timer to tune, and state outside React).
- 2026-10-19: the listener connection is opened lazily, not at startup. Rationale: the API's rule
  that it starts no background job holds, and an idle deployment holds no pooler connection.
