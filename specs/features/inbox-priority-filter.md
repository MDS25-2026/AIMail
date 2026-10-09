# Inbox priority filter

- **Status:** in-progress
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #170
- **Last updated:** 2026-10-09

## Goal

Let the reader narrow the inbox to one priority, so critical and urgent mail can be worked through
without scrolling past the rest. Pairs with the SLA rules floor (#164), which can now mark an email
`critical`.

## User story

As someone triaging a busy inbox, I want to show only critical (or urgent, medium, low) emails, so
that I deal with the most time-sensitive ones first.

## Scope

**In scope**
- A labelled dropdown in the inbox header: All priorities, then every value of `Priority`, using
  the existing `priority.*` strings.
- Client-side filtering of the conversations already loaded; no API change.

**Out of scope**
- Sorting the inbox by priority tier (#142).
- Filtering by category (#141 follow-up).
- Remembering the choice across visits.

## Acceptance criteria

- [ ] Given the inbox, when it loads, then the filter shows "All priorities" and every
      conversation is listed.
- [ ] Given a filter of one priority, when it is chosen, then only conversations whose row (its
      newest email) has that priority are listed, and the header count shows how many.
- [ ] Given a filter that matches nothing, when it is chosen, then the list shows a message naming
      that priority instead of an empty list.
- [ ] Given a selected email that the filter hides, when the filter changes, then the selection
      and the detail panel stay as they were.
- [ ] Given a filter, when the reader presses J/K or the arrow keys in the list, then only the
      listed conversations are stepped through.
- [ ] The options follow the `Priority` type, so a new tier appears without editing the component.
- [ ] The dropdown has an accessible name; strings exist in `en`, `ms` and `zh`.
- [ ] The matching rule is a pure function in `src/lib/` with unit tests.

## Dependencies

- #164 (`critical` priority, merged).

## Edge cases & failure modes

- A thread's row shows its newest email, so the filter uses that email's priority, matching the
  badge the reader sees on the row.
- "Load older emails" adds more conversations; the filter applies to them as they arrive.

## Security & privacy notes

None: filters data already on screen.

## Decisions

- 2026-10-09: Filter on the row's own email priority, not "any message in the thread". Rationale:
  what is filtered matches the badge shown. Alternatives: highest priority in the thread (would
  list rows whose badge does not match the filter).
