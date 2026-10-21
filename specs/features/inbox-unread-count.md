# Inbox: unread count in the header

- **Status:** implemented
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #171
- **Last updated:** 2026-10-19

## Goal

The inbox header says "7 conversations" but not how many of them are new. Add the unread count:
"7 conversations · 3 unread", so the reader sees at a glance how much is waiting.

## Acceptance criteria

- [ ] The count is the unread conversations in the list as shown, so it matches the unread dots:
      the open tab (Primary or Updates, #238) after the priority and category filters, the same
      rows "N conversations" counts.
- [ ] Hidden when nothing listed is unread: "7 conversations" alone.
- [ ] Pluralised in `en`, `ms` and `zh`, reusing the `inbox.unread` string the Updates tab reads
      out to screen readers.

## Edge cases

- **Older pages not loaded:** counted from the loaded pages only, like "N conversations" and the
  Updates tab's count.
- **The Updates tab's own count** stays: it shows unread mail in the tab that is not open.

## Out of scope

- A count in the browser tab title or the sidebar; an unread-only filter.
