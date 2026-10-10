# Quiet hours, send later and snooze

- **Status:** built 2026-10-11 (pending review)
- **Owner:** veyroxie
- **Related issue:** #154 (epic #138, lines 118 to 120)
- **Last updated:** 2026-10-11

## Goal

Help people reply at a decent hour for the person receiving it, schedule a reply that cancels
itself if the other side writes first, and put an email away until it can be dealt with.

## User story

As someone answering mail late at night, I want AIMail to tell me it is 11:40pm for the
recipient and offer to send at 9am their time, so that I respect their evening without having to
remember to send it tomorrow.

## Scope

**In scope**
- **Sender's time offset:** the listener stores the UTC offset from the incoming email's `Date`
  header (`+0800`) on the message. The recipient of a reply is that email's sender, so their
  local time is known.
- **Quiet hours:** a company default (21:00 to 08:00 plus weekend days) set in the admin
  console, and a personal override in Settings. Weekend days are configurable because Kelantan,
  Terengganu and Kedah rest Friday and Saturday, and most other states rest Saturday and Sunday.
- **The suggestion:** pressing Send during the recipient's quiet hours asks "It's 11:40pm for
  them. Send at 8:00am their time instead?" with *Send at 8:00am* and *Send now*: the end of quiet
  hours on their next day that is not a weekend day. It never blocks, and comes after the content
  checks (markers, blanks, tone).
- **Send later:** a menu next to Send: *Tomorrow 9:00am*, *Monday 9:00am*, *Custom time*. The
  server holds the reply and sends it when due. If a new message arrives in the thread first, the
  send is cancelled and the draft comes back with "They replied before your scheduled send.
  Review before sending." A *Scheduled* page lists pending sends, soonest first; opening one shows
  the time and *Cancel*. A scheduled draft is locked: to change it, cancel, edit and schedule again.
- **Snooze:** *Later today*, *Tomorrow 9:00am*, *Next week*, *When quiet hours end*. A snoozed
  email leaves the inbox and returns unread, in its place by date, when due.

**Out of scope**
- Quiet hours delaying holding replies: a holding reply exists to say "got it" quickly.
- Recurring or bulk scheduling; scheduling a brand-new email (AIMail only replies).
- Public holidays (state-by-state calendars); a later extension.

## Acceptance criteria

- [x] Given an email whose `Date` header ends `+0800`, when it is ingested, then the message
      stores an offset of +480 minutes; with no parseable header the offset is null.
- [x] Given a recipient offset and the company quiet hours, when the user presses Send at 23:40
      the recipient's time, then the suggestion shows their local time and the end of their quiet
      hours on the next day that is not a weekend day.
- [x] Given no known offset, then the suggestion uses the user's own timezone and says so
      ("your time").
- [x] Given *Send now* on the suggestion, then the reply goes through the normal send path,
      undo window included.
- [x] Given a scheduled reply, when it falls due and no new message has arrived in the thread,
      then it is sent once through the normal send path with all of its safety checks.
- [x] Given a scheduled reply, when a new message arrives in the thread first, then the send is
      cancelled with the reason and the draft is shown again with the notice.
- [x] Given a scheduled reply, when the user cancels it or schedules it again before it is due,
      then nothing is sent, or it is sent at the new time (one waiting send per email).
- [x] Given a reply that could not be sent when due (backend down), then it is sent when the
      scheduler next runs only if the delay is under 1 hour; otherwise it is cancelled and shown
      again. A late reply can land in the quiet hours it was meant to avoid.
- [x] Given a snoozed email, then it is absent from the inbox until due, and then appears in its
      place, unread.
- [x] Given personal quiet hours, then they replace the company default for that user.

## API surface

- `POST /emails/{id}/schedule` `{draft, send_at}` -> the email with `scheduledFor`.
- `DELETE /emails/{id}/schedule` -> the email, schedule removed.
- `POST /emails/{id}/snooze` `{until}`; `DELETE /emails/{id}/snooze`.
- `GET/PUT /settings/quiet-hours` (personal); the admin console edits the company default.
- `GET /admin/quiet-hours`, `PUT /admin/quiet-hours` (admin console): the company default.
- The email payload gains `senderUtcOffsetMinutes`, `scheduledFor`, `scheduleCancelled`
  (`they_replied` | `too_late` | `refused`, until the reader schedules or sends again) and
  `snoozedUntil`. The Scheduled page filters the inbox data, as Drafts and Sent do.

Changes go into `specs/context/api-contracts.md` in the same PR.

## Data model

- `messages.sender_utc_offset_minutes smallint null`, written by the listener.
- `messages.snoozed_until timestamptz null`.
- `scheduled_send`: `id`, `message_id`, `user_id`, `draft`, `send_at`, `sent_at`,
  `cancelled_reason`, `created_at`. One pending row per message. Modelled on `holding_reply`.
- `quiet_hours`: the company default is the row with no `user_id`; a user's own row overrides it
  (unique on `user_id`, nulls not distinct): `starts`, `ends`, `weekend_days smallint[]` (ISO,
  1 = Monday), `timezone`.

Changes go into `specs/context/db-schema.md` in the same PR.

## Dependencies

- `holding_reply_scheduler.py`: the scheduled-send poller follows its pattern (re-check
  everything when due, cancel with a reason, never send late).
- `approve_and_send`: a scheduled reply goes through it, so the send claim, redaction-marker check
  and audit all apply.
- The listener (Go) for the offset; `net/mail.ParseDate` reads the header.

## Edge cases & failure modes

- **Header lies or is missing:** the offset is a hint for a suggestion only, never a reason to
  block. Missing falls back to the user's timezone.
- **Daylight saving abroad:** the stored offset is the one at the time of their last email; close
  enough for a suggestion.
- **Two tabs schedule the same email:** one pending row per message (unique), second request
  replaces the time.
- **User sends manually while a send is scheduled:** the manual send wins and the schedule is
  cancelled ("sent manually").
- **Edited draft after scheduling:** *Change* reschedules with the new text; the stored draft is
  what goes out.
- **Thread reply arrives during the poll:** the due check reads the thread from Gmail just before
  sending, as holding replies do.

## Security & privacy notes

- The scheduled draft is the masked draft already stored on the message, with the same
  redaction-marker refusal at send time. No new content is stored unmasked.
- The offset says roughly where a sender is; it is shown only to the mailbox owner.
- Erasure removes `scheduled_send` rows with the user's other data (`erasure.py`).

## Open questions

- None open. The other side's reply is read from AIMail's own copy of the thread (the listener
  ingests it within seconds); the owner's own reply, which the listener never stores, is asked of
  Gmail when the send falls due, as holding replies do.

## Out-of-scope future extensions

- Malaysian public holidays per state in quiet hours.
- Learning each contact's usual reply hours instead of a fixed window.

## Implementation notes

- Snooze hides with a filter on the list query (`snoozed_until is null or snoozed_until <= now()`).
- The suggestion is computed on the client from the offset and the quiet-hours settings; the
  server checks nothing about quiet hours, since it is advice.

## Decisions

- 2026-10-10: The recipient's time comes from the offset in their last email's `Date` header.
  Rationale: real local time at almost no cost. Alternatives: the user's own timezone only.
- 2026-10-10: Weekend days are part of quiet hours and configurable. Rationale: Malaysian states
  differ (Friday-Saturday in Kelantan, Terengganu, Kedah).
- 2026-10-10: Default 21:00 to 08:00 plus weekend days, as a suggestion only.
- 2026-10-10: Holding replies ignore quiet hours. Rationale: their job is a fast acknowledgement.
- 2026-10-11: The suggestion offers the end of the recipient's quiet hours (08:00 by default), not a
  fixed 09:00, so it follows the window the company or the user set. *Send later* keeps fixed
  9:00am choices on the reader's own clock.
- 2026-10-11: The Scheduled list filters the inbox data in the browser, as Drafts and Sent do; no
  `GET /scheduled`. A snoozed email returns in its place by date: moving it to the top would change
  the inbox's cursor order.
- 2026-10-11: A scheduled draft is locked until cancelled, so what goes out is what was approved.
- 2026-10-11: The owner answering the thread themselves (from Gmail or anywhere) cancels a waiting
  send (`you_replied`); when Gmail cannot be asked, the send waits for the next pass, bounded by the
  one-hour limit. Rationale: two answers to the same customer.
- 2026-10-11: A reply cannot be scheduled past the day its email's details are deleted
  (`VAULT_RETENTION_DAYS`, 30 days after arrival): its placeholders could not be filled when due.
  Snooze shares the 60-day limit; past that day a snoozed email shows placeholders, not names.
- 2026-10-11: Snooze never hides an email with a reply waiting to go out, so its Cancel stays
  reachable from the Scheduled page.
- 2026-10-11: A scheduled reply goes out through `approve_and_send`, with every check an approved
  reply gets; a check that refuses it when due cancels it with the reason `refused`. A manual send
  cancels any waiting one, so there is never a second copy.
