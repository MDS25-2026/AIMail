# Whole conversations per inbox page, a "You replied" mark, and automated flags for older mail

- **Status:** built 2026-10-13 (relabel: dry run counts 54 emails to flag as automated, 0 the other way; waiting on the owner's yes)
- **Owner:** veyroxie
- **Related issue:** #224 (items S and Z)
- **Builds on:** `conversation-view.md` (the browser groups a thread into one row)
- **Last updated:** 2026-10-13

## Goal

The inbox groups a conversation into one row, but only from the emails already loaded, so a thread
whose older message is on a later page shows twice. A row also gives no sign that the reader already
answered. And emails stored before the automated check learned Gmail's tabs are still flagged as
written by a person.

## Scope

**In scope**

- **`GET /emails` pages by conversation.** A page holds whole threads: the threads whose newest
  visible message is newest, each with every visible message in it, newest first. The cursor is the
  last thread's newest message (`created_at`, `id`), as before, so paging never skips or repeats a
  thread. An email with no `thread_id` is a thread of its own. The page size counts threads. The
  response shape is unchanged, so the browser's grouping, the Sent page and the Scheduled page work
  as they are.
- **"You replied" on a row:** `DashboardEmail.isAnswered` is true when the reader has answered that
  email: sent from AIMail (`sent_at`), or a reply sent from Gmail itself in the same thread after it
  arrived (`sent_message`). The row shows a quiet "You replied" mark on the conversation's newest
  email, with an icon and words. A newer email from the other person is not answered, so the mark
  goes away when they write back.
- **`go run . relabel`** (listener) re-checks `is_automated` on stored emails with today's rules,
  reading only each email's labels and the headers the rules use (a Gmail metadata read, never the
  body). Dry run by default; `--write` needs the owner's yes.

**Out of scope**

- Grouping the Drafts, Sent or Scheduled pages; they keep listing individual emails.

## Acceptance criteria

- [ ] Given a thread whose older email would fall on page 2 by itself, then page 1 holds both emails
      and page 2 holds neither.
- [ ] Given 3 threads and a page size of 2, then page 1 holds the 2 newest threads and page 2 the third.
- [ ] Given an email answered from AIMail, or one followed in its thread by a reply sent from Gmail,
      then `isAnswered` is true; given the other person wrote again after the reply, the newer email
      is not answered.
- [ ] Given `relabel` without `--write`, then nothing is written and it prints how many flags would
      change.

## API surface

- `GET /emails`: same shape; each page holds whole threads; `limit` counts threads.
- `DashboardEmail` gains `isAnswered: bool` (list rows; false elsewhere). Additive.

## Data model

None.

## Decisions

- 2026-10-13: Page by thread on the server but keep a list of emails in the response, not one row per
  thread. The Sent and Scheduled pages read the same list, and the browser's grouping already does the
  rest; a new response shape would have changed three pages for the same result.
