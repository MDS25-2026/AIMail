# Conversation view: one row per thread, the whole conversation in one place

- **Status:** built 2026-10-05 (owner: "copy how Gmail handles emails within the same thread")
- **Owner:** veyroxie; Lane D (Han) for the dashboard, Lane B for the contract fields
- **Related:** [api-contracts.md](../context/api-contracts.md) `DashboardEmail.threadContext`,
  [restorable-masking.md](./restorable-masking.md) (details apply to every message shown)
- **Last updated:** 2026-10-05

## Goal

Reading a back-and-forth should not mean hopping between Inbox and Sent. Like Gmail, the inbox shows
each conversation once, and opening it shows every message, the owner's own replies included, in
order, with the newest open and ready to reply to.

## Behaviour

1. **Inbox, one row per conversation.** Rows sharing a Gmail thread collapse into the newest one,
   with the number of messages beside the sender ("Aisyah (3)"). The row is unread if any message in
   it is. Drafts and Sent keep listing individual emails.
2. **Detail, the conversation stacked.** Earlier messages sit above the open one as one-line cards
   (sender, time, first line); clicking one expands its full body. The owner's replies sent from
   AIMail appear in place as "You", with the time they were sent. The open message is expanded,
   followed by its draft.
3. **Restored details** (restorable masking) are highlighted in every expanded message, and Hide
   details applies to all of them.
4. **Unchanged:** what the AI sees (still the latest five earlier messages, by position, never by
   sender), the extension panel (Gmail shows the thread beside it), and every route's scope.

## Contract (`specs/context/api-contracts.md`)

- `DashboardEmail.threadId: string | null`: the Gmail thread id, so the dashboard can group rows.
- `ThreadMessage` gains `body` (the full masked body, placeholders renumbered for the thread) and
  `timestamp` (received time; for the owner's reply, the time it was sent). Detail responses only.

## Acceptance criteria

- [ ] Three emails in one thread show as one inbox row with "(3)", unread if any of them is.
- [ ] Opening it shows the two earlier messages collapsed above the newest, and the owner's reply in
      place as "You"; clicking a collapsed card shows its full body with details restored.
- [ ] Drafts and Sent still list every email individually.

## Estimate

Half a day.
