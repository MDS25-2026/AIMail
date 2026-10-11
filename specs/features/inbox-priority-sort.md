# Inbox sorted by priority

- **Status:** in-progress
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #142
- **Last updated:** 2026-10-11

## Goal

The SLA rules floor (#164) marks time-sensitive mail `critical`, but the inbox still lists
everything newest first, so a critical email can sit below a page of newsletters. List the most
urgent conversations first, as #142 asks, and keep "newest first" one click away.

## User story

As someone triaging a busy inbox, I want critical and urgent emails at the top, so that I deal with
them before anything else.

## Scope

**In scope**
- A labelled "Sort" dropdown in the inbox header: Most urgent first (the default) and Newest first.
- Most urgent first: by the row's priority (critical, urgent, medium, low), newest first within each
  tier. Client-side, over the conversations already loaded; no API change.
- Works together with the priority and category filters, and J/K follows the listed order.

**Out of scope**
- The rules floor itself (#164, merged) and the backend parts of #142.
- Sorting on the server, so that urgent mail not yet loaded comes first.
- Remembering the choice across visits.

## Acceptance criteria

- [ ] Given the inbox, when it loads, then the sort shows "Most urgent first" and critical rows are
      listed before urgent, then medium, then low.
- [ ] Given two rows with the same priority, then the newer one is listed first.
- [ ] Given "Newest first", when it is chosen, then the rows are in the order they arrived, as
      before this change.
- [ ] Given a priority or category filter, then the remaining rows keep the chosen sort.
- [ ] Given a sort, when the reader presses J/K or the arrow keys in the list, then they step
      through the rows in the order shown.
- [ ] A thread is placed by its row's email (its newest), matching the badge on the row.
- [ ] The dropdown has an accessible name; strings exist in `en`, `ms` and `zh`.
- [ ] The ordering is a pure function in `src/lib/` with unit tests.

## Dependencies

- #164 (`critical` priority, merged); #170 (priority filter, merged).

## Edge cases & failure modes

- Only loaded emails are sorted: a critical email older than the loaded page appears only after
  "Show older emails", then moves to the top.
- A new urgent email arriving while the inbox is open moves to the top of its tier, so rows below it
  shift; the selection follows the email, not the position.

## Security & privacy notes

None: reorders data already on screen.

## Decisions

- 2026-10-11: Most urgent first is the default. Rationale: #142 asks for the inbox sorted by tier,
  and it is the point of the rules floor. Alternatives: newest first by default, with urgency as the
  option (what Gmail does, but hides critical mail below the fold).
- 2026-10-11: Rely on the list arriving newest first and a stable sort, rather than comparing
  timestamps. Rationale: the API already orders by received time; one comparison fewer to keep in
  step with it. Alternatives: sort on `timestamp` within each tier.
