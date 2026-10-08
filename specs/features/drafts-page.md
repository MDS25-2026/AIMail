# Drafts page: every reply the AI has written that has not gone out

- **Status:** approved (Han, 2026-10-08) — build after #168 merges
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #169
- **Last updated:** 2026-10-08

## Goal

`/drafts` is a `ComingSoon` stub. Make it list every email that has an AI draft waiting for
approval, so the reader can find unsent replies without scrolling the inbox.

## User story

As someone reviewing AI replies, I want one list of every draft that has not been sent, so that I
can work through them and none is forgotten.

## Scope

**In scope**
- `/drafts` renders `FilteredEmailList` (the component `/sent` already uses) over the cached
  `/emails` list, filtered client-side.
- A draft qualifies when it has text, has not been sent, and the inbox would show it for review.
- New `drafts.*` strings in `en`, `ms` and `zh`.

**Out of scope**
- Editing or sending from the Drafts page — a row opens the email in the inbox, where the draft
  controls and the approval step already live.
- Reminders for old drafts (#155).
- Any backend or API change.

## Acceptance criteria

- [ ] Given an email with a non-empty `draftReply` and no `sentAt`, when the reader opens
      `/drafts`, then it is listed.
- [ ] Given an email with `sentAt` set, when the reader opens `/drafts`, then it is not listed.
- [ ] Given an email with an empty `draftReply` (never generated, or the agent wrote none), when
      the reader opens `/drafts`, then it is not listed.
- [ ] Given an email with `authStatus` `spoof_detected`, when the reader opens `/drafts`, then it
      is not listed (the detail panel hides its draft behind `SecurityNotice`).
- [ ] Given an email with `masking` `pending` or `abandoned`, when the reader opens `/drafts`,
      then it is not listed (the detail panel shows `QuarantineNotice` instead of a draft).
- [ ] Given an email with `isDrafting` true (its draft is queued, #168), when the reader opens
      `/drafts`, then it is not listed until the draft is written.
- [ ] Given a listed draft, when the reader clicks its row, then the inbox opens with that email
      selected (`/?email=<id>`).
- [ ] Given no qualifying drafts, when the reader opens `/drafts`, then an empty state explains
      that drafts appear once an email has been opened or pre-generated.
- [ ] Given the list is loading or failed, when the reader opens `/drafts`, then the existing
      `PageLoading` / `PageError` states show.
- [ ] The filter rule is a pure function in `src/lib/` with unit tests for each case above.
- [ ] `tsc`, eslint and vitest pass; every new string exists in all three locales.

## API surface

None new. Reads `GET /emails` through the existing `useEmails()` query. The list response
already carries the stored `draftReply` (`backend/app/dashboard.py`).

## Data model

None.

## Dependencies

- `FilteredEmailList`, `PageState`, `useEmails()` — all existing.
- #162 (`AuthStatus`), #109 (`masking` quarantine states).
- #168 (open): paginated `useEmails()` with "load older" in `FilteredEmailList`, queued drafts
  (`isDrafting`), and email types generated from the backend schema. Build on top of it.

## Edge cases & failure modes

- A draft is generated when an email is first opened (or by pre-generation), so a brand-new
  email has no draft yet and does not appear until then. The empty-state text says so.
- With #168's pagination, only loaded pages are filtered; "load older" reaches the rest, as on
  `/sent`.
- The list row shows the stored draft, which can contain placeholders such as `[PERSON_1]`:
  the list response carries no `details`, so names are not restored here. Same as `/sent` today.

## Security & privacy notes

Shows only what the inbox list already shows (masked content). Excluding spoofed and
quarantined emails keeps the page from surfacing drafts the detail panel deliberately withholds.

## Open questions

None.

## Implementation notes

- `isPendingDraft(email: Email): boolean` in `src/lib/` keeps the rule testable.
- `timestampOf` = the email's received `timestamp`.

## Decisions

- 2026-10-08: Reuse `FilteredEmailList` rather than port the Lovable prototype's row layout.
  Rationale: Han chose main's layout (decision F); one component for Drafts and Sent.
  Alternatives: prototype rows with "To {sender}", two draft lines and a critic badge.
