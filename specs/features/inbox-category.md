# Inbox category badges and filter

- **Status:** in-progress
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #193 (dashboard half of #141)
- **Last updated:** 2026-10-09

## Goal

Show what kind of email each one is (client, vendor, internal, security, admin, personal), from the
classifier (#141, stored once per email since #186), and let the reader filter by it.

## User story

As someone working through the inbox, I want to see and filter emails by kind, so that I can deal
with, say, all vendor mail together.

## Scope

**In scope**
- A neutral category badge (icon + word) next to the priority badge on each inbox row.
- A category dropdown beside the priority filter (#170); the two combine.
- No badge for an unclassified email or an unsure classification.

**Out of scope**
- The detail panel header and the extension side panel.
- Correcting a category by hand.
- A newsletter / automated category (deferred to #147).

## Acceptance criteria

- [ ] Given an email with `categoryConfidence` ≥ 0.5, when the inbox shows it, then its row has
      the category's badge (icon + translated word).
- [ ] Given an email with no `categoryConfidence` (not yet classified; the API sends `internal` as
      a placeholder), when the inbox shows it, then its row has no category badge.
- [ ] Given an email with `categoryConfidence` below 0.5, then its row has no category badge.
- [ ] Given a category filter, then only rows whose shown category matches are listed;
      unclassified and unsure rows appear only under "All categories".
- [ ] Given both filters, then a row is listed only if it matches both; if none match, the list
      says so.
- [ ] The options follow `EmailCategory`, so a new category fails to compile until it is placed.
- [ ] Badge colours are palette tokens; strings exist in `en`, `ms` and `zh`; the rules are pure
      functions with unit tests.

## Dependencies

- #186 (categories stored by the worker; `categoryConfidence` null until classified).
- #189 (priority filter): this branch builds on it.

## Edge cases & failure modes

- Until the worker's first pass, every email is unclassified, so the inbox shows no category
  badges at all rather than a wall of "Internal".
- A missing model file stores nothing (#186), so the same no-badge state applies.

## Security & privacy notes

Shows only the stored label and confidence; the classifier only ever saw masked text.

## Decisions

- 2026-10-09: No badge when unclassified or unsure, rather than "Uncategorised" or the API's
  `internal` default. Rationale: a wrong label is worse than none (Han, agreed on #167).
  Alternatives: a neutral "Uncategorised" badge.
- 2026-10-09: Threshold 0.5, one constant (`CATEGORY_MIN_CONFIDENCE`). Rationale: below it, the
  six-way classifier's top guess is less likely than all the others combined. Tunable once real
  confidences are seen.
- 2026-10-09: Neutral styling (outline, muted text). Rationale: category is context, priority is
  the call to action; six category colours would also have to pass the colour-blind checks.
