# To-do: what needs me

- **Status:** draft
- **Owner:** veyroxie
- **Related issue:** #155 (epic #138, line 121); action types requested on #142
- **Last updated:** 2026-10-10

## Goal

One page that answers "what needs me?": emails asking something of the reader, drafts the AI is
unsure of, replies still waiting for an answer, and drafts never sent. Today the first two only
show inside an opened email, and the last two show nowhere.

## User story

As a busy mailbox owner, I want one list of everything waiting on me or on someone else, so that
nothing falls through the cracks between opening emails.

## Scope

**In scope**
- A **To-do** page in the navigation, with one count on the nav item (sum of sections 1, 2, 4,
  and the overdue part of 3).
- **1. Needs your action:** unsent emails whose `action_items` are not empty, the items listed.
  Grouped by action type once the team adds one (#142); until then, ungrouped.
- **2. Needs your review:** unsent emails with `needs_human_review`, with the review reason.
- **3. Waiting for their reply:** replies sent by the user that ask something, with no new message
  in the thread after `WAITING_DAYS` (default 3) working days. Clears itself when anything arrives
  in the thread. *Draft a follow-up* writes a nudge in the thread's language, reviewed and sent the
  normal way, never automatically. *Not waiting* removes one.
- **4. Drafts you haven't sent:** a reminder, not a second drafts list. Only drafts ready for
  more than 24 hours and not sent, with *Open*, *No reply needed*, and *See all drafts* linking to
  `/drafts` (#169, the full list). Emails with `authStatus = spoof_detected` are left out, as on
  `/drafts`.
- **Replies sent from Gmail count too:** the listener also watches the Sent label, masks those
  emails like incoming mail, and stores them in their own table, so nothing that reads `messages`
  (the drafter, the inbox, search) can pick them up.
- **"Asks something":** word rules in English, Malay and Chinese ("?", please confirm, could you,
  boleh, sila, mohon, 请, 能否, 是否). Replies sent through AIMail also get a *Remind me if no
  reply* box beside Send, ticked when the rules match, which the user can change.
- **Working days** follow the weekend days in quiet hours (`quiet-hours-send-later.md`).
- `WAITING_DAYS` is a personal setting.

**Out of scope**
- Action types (pay, sign, attend, ...): the team's triage work (#142). The page groups by the
  field once it exists.
- Sorting by deadline: #142's priority, used once it lands; until then newest first.
- Sending a follow-up automatically.
- The full list of unsent drafts: the Drafts page (#169).

## Acceptance criteria

- [ ] Given an unsent email with action items, then it is in section 1 with its items.
- [ ] Given an unsent email flagged for review, then it is in section 2 with its reason.
- [ ] Given a reply sent through AIMail with *Remind me* ticked, when 3 working days pass with no
      new message in the thread, then it is in section 3.
- [ ] Given a reply sent from Gmail that matches the rules, then the same holds.
- [ ] Given a reply in section 3, when any message arrives in the thread, then it leaves section 3.
- [ ] Given "Thanks, received!" sent with no question, then it never enters section 3.
- [ ] Given a Friday-Saturday weekend in quiet hours, then those days do not count.
- [ ] Given a draft ready for over 24 hours and not sent, then it is in section 4 until sent,
      dismissed with *No reply needed*, or replaced by a newer message.
- [ ] Given a sent email stored from the Sent label, then it never appears in the inbox and is
      never drafted for.
- [ ] Given *Draft a follow-up*, then a draft appears for review in the thread's language and
      nothing is sent.

## API surface

- `GET /todo` -> `{needsAction[], needsReview[], waiting[], unsentDrafts[], count}`.
- `POST /todo/waiting/{id}/dismiss`; `POST /emails/{id}/dismiss` (no reply needed).
- `POST /todo/waiting/{id}/follow-up` -> a draft for review.
- `POST /emails/{id}/send` gains `remindIfNoReply: boolean`.
- `GET/PUT /settings/todo` `{waitingDays}`.

Changes go into `specs/context/api-contracts.md` in the same PR.

## Data model

- `sent_message`: `id`, `user_id`, `gmail_id` (unique), `thread_id`, `sent_at`, `subject`,
  `body_masked`, `asks_something`, `remind` (null = rules decide), `dismissed_at`. Written by the
  listener for Gmail sends and by the backend for AIMail sends.
- `messages.dismissed_at timestamptz null` (no reply needed).
- `user_preferences.waiting_days smallint default 3`.

Changes go into `specs/context/db-schema.md` in the same PR.

## Dependencies

- Listener (Go): watch and history on `SENT` as well as `INBOX`; today `isOwnSentReply` skips
  these. Same masking path, quarantine included.
- `quiet-hours-send-later.md` for weekend days.
- The agent for the follow-up draft (an instruction on the thread, like refine).

## Edge cases & failure modes

- **A reply sent through AIMail also arrives via the Sent label:** one row, matched on `gmail_id`.
- **Sent to several people, one answers:** any new message in the thread clears it.
- **Thread with only an automatic "out of office" back:** clears it (it is a new message);
  accepted, since telling auto-replies apart is unreliable.
- **Masking down:** a sent email is quarantined like an inbound one; it joins the list once
  masked.

## Security & privacy notes

- Sent mail is masked before storage, exactly like incoming mail; nothing unmasked is stored.
- Watching Sent means storing more of the user's mail. The privacy notice and erasure cover
  `sent_message`.

## Decisions

- 2026-10-10: Replies sent from Gmail are included. Rationale: otherwise the list misses most of
  what people send. Alternatives: AIMail sends only.
- 2026-10-10: Only replies that ask something are tracked. Rationale: "Thanks!" has nothing to
  wait for.
- 2026-10-10: `WAITING_DAYS` defaults to 3 working days and is a setting.
- 2026-10-10: Sent mail lives in its own table. Rationale: no existing reader of `messages` can
  treat it as received mail.
- 2026-10-10: Action types are left to the team (#142); the page groups by them when they exist.
- 2026-10-10: Section 4 only reminds about drafts older than 24 hours and links to `/drafts`
  (#169). Rationale: one list of drafts, not two.
