# Import past emails when a mailbox is first connected

- **Status:** accepted 2026-10-21 (owner chose every recommended answer below)
- **Owner:** veyroxie (spec, listener, backend); dashboard reviewed by HyperByte12263 (Han), listener by JiaJun
- **Related issue:** epic #138
- **Last updated:** 2026-10-21

## Why an inbox looked empty (diagnosis, 2026-10-21)

A user connected on 21 Oct 09:28 UTC and saw an empty inbox. The database shows the listener worked:
`start_mailbox` at 09:29:22, then `seedInbox` stored the newest 10 inbox emails between 09:29:23 and
09:29:32, all masked (`complete`), none quarantined. All 10 were automated mail (newsletters,
notifications), and since #240 automated mail is listed under Updates, so the Primary tab was empty.

Not a listener bug. Two gaps: 10 emails is too few, because a real inbox's newest are mostly
automated; and an empty Primary tab gives no hint that the mail is under Updates.

## Goal

A newly connected user sees a useful slice of their existing inbox, not only mail that arrives later.

## User story

As someone who just connected Gmail, I want my recent emails in AIMail within a minute or two, so
that I can try it on real mail straight away.

## Decisions (accepted 2026-10-21)

1. **How much:** the newest 20 inbox emails from the last 30 days, whichever limit comes first
   (owner, 2026-10-21: 20 rather than 50, a first look that fills fast). Cost: one list call plus one get per email (about 5 quota units each, far under Gmail's
   per-user limit), one Presidio pass per email, and the attachment reader for those with attachments.
2. **AI drafts:** none for imported mail. The background drafter skips emails received before the
   mailbox was connected (`mailbox_connection.created_at`, kept on reconnect). Opening one still
   drafts it on request, as today. No schema change.
3. **Progress:** no progress bar. 20 emails take well under a minute at a concurrency of 3; the inbox fills
   as they land. Instead, an empty Primary tab says how many emails are under Updates, with a link.
4. **Attachments:** read as for any email, through the same `maskMessage` path, so imported mail is
   masked exactly like new mail. Skipping them would need a second path for no great saving at 20.
5. **Reconnect:** importing runs only on a mailbox's first start (`history_id` empty). Signing in again
   keeps the baseline, so nothing is imported twice; stored rows are skipped by the batched lookup and
   the insert's `on_conflict=user_id,gmail_message_id`. Disconnecting deletes everything, so connecting
   again later is a first connection and imports afresh.

## Scope

**In scope**
- Listener: `importInbox` replaces `seedInbox`. Lists `in:inbox newer_than:<days>d` with `pageToken`
  paging until the cap; drops already-stored ids in one batched lookup (`newMessages`); ingests the rest
  in a bounded worker pool (default 3), outside the mailbox's `ingesting` lock; backs off on 429 and 5xx.
  Each email goes through `ingestUnstored` and `maskMessage`, so NER down means a quarantined row with
  no content, as in #109. One audit row when the import finishes: counts only.
- Backend: the background drafter's claim skips mail received before its mailbox was connected.
- Dashboard: an empty Primary tab with mail under Updates says so and links to Updates (en, ms, zh).
- Settings (env, optional): `IMPORT_MESSAGE_LIMIT` (20), `IMPORT_DAYS` (30), `IMPORT_CONCURRENCY` (3).

**Out of scope**
- Importing Sent mail or other labels; re-importing on demand; a progress indicator.

## Acceptance criteria

- [ ] Given a first start, then the newest emails up to the cap are listed across pages and stored.
- [ ] Given more than the cap in Gmail, then exactly the cap is fetched.
- [ ] Given some already stored, then only the rest are fetched.
- [ ] Given Presidio down, then each imported email is stored as a quarantined row with no content.
- [ ] Given a 429 from Gmail, then the listener waits and retries, and gives up after a bounded number.
- [ ] Given a reconnect (baseline kept), then nothing is imported.
- [ ] Given imported mail, then the background drafter does not draft it; a requested draft still works.
- [ ] Given an empty Primary tab and mail under Updates, then the inbox says so and links to Updates.
- [ ] Other mailboxes keep ingesting while one imports (bounded pool, no mailbox lock held).

## Data model

No change. The drafter reads the existing `mailbox_connection.created_at` and `messages.received_at`.

## Security and privacy

Every imported email is masked in the listener before storage, by the same path as new mail. Nothing
new reaches a model: no drafts are generated for imported mail unless the user asks for one.
