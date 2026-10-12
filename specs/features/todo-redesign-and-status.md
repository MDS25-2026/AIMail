# To-do redesign and a service status page

- **Status:** in progress 2026-10-12
- **Owner:** veyroxie
- **Related issue:** #224 Phase 1 (items A to J, and T16 from the 12 Oct test run)
- **Builds on:** `todo-page.md` (the four lists, dismiss, waiting, follow-ups)
- **Last updated:** 2026-10-12

## Goal

The To-do page should tell a busy person what to do next, offer one obvious way to do it, and let
them finish. Today every row looks the same, every list is open at once (the tester had to scroll
through all of them, T16), and there is no sense of progress. Separately, anyone should be able to
see whether AIMail's parts are working without signing in.

## User stories

- As a mailbox owner, I want each to-do to say what to do next, so that I don't have to open the
  email to find out.
- As a mailbox owner, I want to see how much is left and what I've done today, so that I know when
  I'm finished.
- As a tester or teammate, I want a public status page, so that I can tell "it's broken" from "it's
  my account".

## Scope

**In scope**

- **Sections you enter (T16, D, G).** One tab per list, each with its count:
  **Reply needed** (was *Needs your action*), **Check before sending** (*Needs your review*),
  **Drafts you started** (*Drafts you haven't sent*), **Waiting on others** (*Waiting for their
  reply*). The tab is kept in the address (`/todo?tab=review`), so Back and a shared link work. The
  page opens on the first tab with anything in it. A tab with nothing in it stays visible with 0, so
  the four places don't move around.
- **Rows that say what to do next (A).** The first line starts with a verb:
  - Reply needed: the first action item as written (they start with a verb: "Confirm the refund
    date"), with "+N more" when there are several; with no action item, "Reply: {one-line summary}";
    with neither, "Reply: {subject}". Never an empty verb.
  - Check before sending: "Check the draft: {first review reason}".
  - Drafts you started: "Send or drop your draft".
  - Waiting on others: "Follow up: no answer in N working days".
  The sender and subject move to a second, quieter line.
- **One main button per row; the rest in a menu (B).** Main button: **Reply**, **Review draft** or
  **Open draft** opens the email; **Draft follow-up** (or **Open in Gmail** for a reply sent from
  Gmail) on a waiting row. The menu (an icon button named "More actions") holds **Remind me later**,
  **No reply needed** / **Not waiting**, and **Open in Gmail**. On a phone the menu opens as a sheet
  along the bottom of the screen. Targets are at least 44 px on a phone.
- **Show less, reveal on demand (D).** Each tab shows 5 rows, then "Show N more". A row's "Show more"
  expands it in place: the summary, every action item, and the first lines of the draft. Opening the
  email is the second level.
- **Ordered by urgency (E).** Within a tab: priority (critical, high, medium, low), then oldest
  first. The row shows the priority badge for critical and high only.
- **Undo instead of "are you sure?" (C).** No reply needed, Not waiting and Remind me later remove
  the row at once and show "{what} · Undo" for 8 seconds. Undo calls the matching reverse route.
- **Remind me later (H).** Later today, Tomorrow morning, Next week, and (when quiet hours are set)
  When my working hours start, the same choices as the email's Snooze, from one shared helper. A
  snoozed email leaves the To-do lists until it is due.
- **Progress and finishing (F).** A line under the heading: "{done} done today · {left} left". When
  nothing is left, an **All clear** panel says what will appear here (emails that ask something of
  you, drafts to check, replies waiting on others) and links to the inbox. This also serves a new
  user with nothing yet (I).
- **Status page (J).** A public page at `/status`, outside the signed-in app shell, linked from the
  landing page's footer as "Service status". One row per part: Dashboard, Backend, Database,
  Personal-detail masking, AI drafting, Mail listener. Each row has an icon and words (Working, Slow
  to respond, Not working), never colour alone, and "Checked {n} s ago". It refreshes every 30 seconds
  and pauses while the tab is hidden.

**Out of scope (and why)**

- **Due badges ("Overdue", "Due Fri").** `messages.deadline_at` is never filled in (0 of 238 stored
  emails on 2026-10-12); deadline parsing is the team's SLA work (#142). Badges would never appear,
  so none are built. Rows sort by priority instead.
- **"Approve & send" from a row.** The email view's send path carries the undo countdown, the
  marker and template-gap guards and the send-permission check; a second, one-click path would
  bypass them. **Review draft** opens the email at the draft instead.
- **"Draft reply" from a row.** Opening the email already drafts one when there is none.
- Status history and uptime bars (#224 Q), action-item checklists (L), focus mode (M), shortcuts and
  swipes (N).

## Acceptance criteria

- [ ] Given four lists with 2, 0, 1 and 3 items, when the reader opens `/todo`, then four tabs show
      2, 0, 1 and 3, the first tab is selected, and only its rows are shown.
- [ ] Given the reader picks *Waiting on others*, then the address reads `?tab=waiting`, and
      reloading keeps that tab.
- [ ] Given an email with action items "Confirm the refund date" and "Send the invoice", then its
      row reads "Confirm the refund date +1 more", with the sender and subject below.
- [ ] Given an email in *Reply needed* with no action items left and no summary, then the row reads
      "Reply: {subject}".
- [ ] Given 8 rows in a tab, then 5 show with "Show 3 more", which shows the rest.
- [ ] Given a critical email received yesterday and a low one received last week, then the critical
      one is first.
- [ ] Given the reader chooses *No reply needed* from a row's menu, then the row and one from the
      tab's count and the nav count go at once, and "Dismissed · Undo" shows; Undo brings the row
      back and the server clears `dismissed_at`.
- [ ] Given the reader chooses *Not waiting*, then the same, and Undo clears the reply's
      `dismissed_at` (new route below).
- [ ] Given the reader chooses *Remind me later → Tomorrow morning*, then the row leaves the list,
      the email is snoozed until 9:00 tomorrow in the reader's time zone, and Undo wakes it.
- [ ] Given the reader sent one reply and dismissed two emails today (their time zone), then the
      progress line reads "3 done today"; undoing one dismissal makes it 2.
- [ ] Given every list is empty, then the All clear panel shows instead of tabs.
- [ ] Given a signed-out visitor opens `/status`, then the page loads without sending them to
      sign-in, and shows six rows.
- [ ] Given Presidio does not answer, then *Personal-detail masking* reads "Not working" with its
      icon, and the other rows still show their own state.
- [ ] Given the listener last renewed a mailbox's watch 30 hours ago, then *Mail listener* reads
      "Slow to respond"; after 50 hours, "Not working".
- [ ] Given the reader uses a phone, then the row menu opens as a bottom sheet and every target is
      at least 44 px.
- [ ] Every new string exists in English, Malay and Chinese.

## API surface

- `GET /todo` gains `doneToday: int`. Counted from live columns, not the audit log, so an undo
  lowers it: emails sent today, emails dismissed today, replies marked *Not waiting* today, and
  follow-ups sent today. "Today" starts at midnight in the reader's quiet-hours time zone.
- `GET /todo`: snoozed emails (until a future time) are left out, as in the inbox.
- `DELETE /todo/waiting/{id}/dismiss` (new, 204): undoes *Not waiting*; 404 for another owner's or
  an unknown id. Audited as `waiting_dismissed` with `dismissed: false`, like the email undo.
- `GET /service-status` (new, public, no sign-in): `{"checkedAt": iso, "parts": {"backend": state,
  "database": state, "masking": state, "drafting": state, "listener": state}}` where state is `ok`,
  `degraded` or `down`. The dashboard row is the page itself loading. Results are cached for 15
  seconds, so visitors cannot make it call Presidio or the agent more often. Always 200: the states
  carry the news. `/healthz` and `/readyz` are unchanged (Render probes `/healthz`).
  - **drafting:** the agent's `/healthz` on its loopback address answers.
  - **listener:** when it last renewed a Gmail watch: the newest `watch_expires_at` among mailboxes
    that don't need reconnecting, minus Gmail's 7-day watch lifetime. Only the listener writes that
    column, at start and on its daily renewal, so a quiet inbox still checks in daily. `degraded`
    after 26 hours, `down` after 50. With no connected mailbox, `ok` is not claimed: `degraded`.

## Data model

None. No migration.

## Dependencies

- Existing: `POST/DELETE /emails/{id}/dismiss`, `POST /emails/{id}/snooze` and its wake, the
  waiting dismiss, `quiet_hours.settings_for`.

## Edge cases & failure modes

- **Undo after the 8 seconds:** the notice is gone; the email can be found in the inbox as before.
- **Undo fails:** the row stays removed and the notice says the undo didn't go through.
- **Dismiss fails:** the row and both counts come back (already built in #226), with the error.
- **Two removals within 8 seconds:** the newer notice replaces the older one; the first stays done.
- **A tab named in the address that doesn't exist:** the first tab with anything in it.
- **Status endpoint slow part:** each check has the existing 2-second timeout and runs in parallel,
  so one slow part shows `down` rather than delaying the page.
- **Status page while the backend itself is down:** the request fails, and every server-side row
  reads "Not working"; the dashboard row reads "Working" because the page loaded.

## Security & privacy notes

- `/service-status` says only which part is working; no counts, addresses, ids or timestamps beyond
  the check time. The listener's state is a bucket, not the stored time.
- It is public by design. The 15-second cache keeps it from being an amplifier against Presidio or
  the agent.
- Row text uses the same per-row details as today, so names show where the inbox shows them.

## Decisions

- 2026-10-12: The status data gets its own route instead of new `/readyz` checks. `/readyz` means
  "ready for traffic"; a stale listener or a stopped agent must never mark the backend unready.
- 2026-10-12: The listener's state comes from `mailbox_connection.watch_expires_at`, which only the
  listener writes. Not `updated_at` (a sign-in stamps it, so a stopped listener would look alive), not
  the newest audit row (a quiet inbox would read as down), not a heartbeat table (a schema change).
- 2026-10-12: "Done today" comes from live columns, so Undo lowers it; the audit log keeps rows for
  actions that were later undone.
- 2026-10-12: Empty tabs stay visible with 0, so the four tabs keep their places.
