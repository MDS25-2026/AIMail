# Inbox: Primary and Updates tabs

- **Status:** implemented
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #238 (split from #147)
- **Last updated:** 2026-10-18 (review fixes)

## Goal

The listener already marks newsletters and notifications as automated (`listener/automated.go`),
and AIMail neither drafts for them nor puts them on the To-do. The inbox still lists them among mail
from people, so the reader scrolls past them to find what needs them. Keep them in a tab of their
own, one click away.

## User story

As someone working through my inbox, I want newsletters and notifications kept apart from mail
written to me, so that the inbox shows what needs me, and the rest is there when I want it.

## Scope

**In scope**
- A **Primary / Updates** switch at the top of the inbox list, under the heading and conversation
  count, above the priority and category filters.
  - **Primary**, the default, lists conversations whose newest email is not automated.
  - **Updates** lists those whose newest email is (`email.isAutomated`), the rule the priority and
    category filters already use for a conversation.
- The Updates tab shows its **unread count**, so mail there is never out of mind. Primary shows
  none: its unread rows are already marked in the list.
- Sort, priority and category apply **within** the open tab and stay set when switching.
- The tab is in the URL, `?view=updates` (Primary has none), so Back and shared links keep it, as
  the To-do's `?tab=` does.
- An email opened by `?email=` (from Sent, To-do or a search) shows the tab its conversation is
  listed under, also when it is older than the loaded pages (its detail tells).
- In Updates, one line under the switch: "Newsletters and notifications. AIMail doesn't draft
  replies for these." Each tab has its own empty state.
- Proper tabs: `role="tablist"` / `tab` / `tabpanel`, `aria-selected`, arrow keys move between
  them, as on the To-do page. They fit a 375px phone.
- J/K and the arrow keys move through the open tab's list only.
- The demo mailbox (#227) gets the payslip notice unread, so the Updates count shows there too.
- Strings in `en`, `ms` and `zh`.

**Out of scope**
- "Move to Primary" for a wrongly flagged email: keeping the reader's correction needs a backend
  field. A later issue.
- First-time sender screening (#239).
- The extension panel, To-do and Sent: unchanged.
- Any API, database or listener change.

## Acceptance criteria

- [ ] Given the inbox opens, then Primary is selected and no conversation whose newest email is
      automated is listed.
- [ ] Given Updates is selected, then only those conversations are listed, and the tab shows how
      many of them are unread.
- [ ] Given a priority or category filter, or Newest first, when the reader switches tab, then it
      still applies.
- [ ] Given `/?view=updates`, then Updates opens; given `/?email=<id>` for an automated email,
      then its row is shown in Updates.
- [ ] Given the keyboard, then Left/Right move between the tabs, and J/K stay within the open tab.
- [ ] Given a 375px screen, then the switch and the filters fit without scrolling sideways.
- [ ] Strings exist in all three languages; colours are palette tokens only.

## Dependencies

- `email.isAutomated` from the listener (#162, #225); the conversation grouping (#231); the sort
  (#213) and filters (#189, #194).

## Edge cases & failure modes

- **An older email flagged before the listener checked these headers:** #231 back-filled the
  flag for older mail; anything it missed stays in Primary, the safe side.
- **A real email flagged as automated** (Gmail put it in its Updates tab): it is in Updates, still
  readable, and Regenerate still drafts a reply. Moving it back is the out-of-scope follow-up.
- **No automated mail:** Updates shows its empty state; the switch stays, so the reader learns
  where such mail goes.
- **Desktop opens an email beside the list:** the open tab's newest conversation, by its newest
  email; never an older email of a thread listed under the other tab.
- **The Updates count covers the loaded pages only;** Load older may bring more.
- **Page 1 all newsletters:** Primary shows no "Nothing from people" while Load older may still
  bring some.

## Security & privacy notes

- Display only: the same emails, split differently. Nothing new is fetched, stored or sent.

## Decisions

- **Tabs, not a fourth dropdown, a collapsed row or a sidebar page** (Han, 2026-10-18). Tabs hide
  newsletters by default yet keep them one click and a count away; the header already holds three
  dropdowns; a collapsed row complicates J/K and sorting; a sidebar page puts them out of sight
  and takes a slot on the phone's bottom bar.
- **"Updates", not "Newsletters"** (Han, 2026-10-18): the flag also covers payslips, receipts
  and no-reply notices, and Gmail uses the same word.
