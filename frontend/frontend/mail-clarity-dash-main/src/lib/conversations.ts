import type { Email, ThreadMessage } from "../types/email";

/** One inbox row per conversation, as Gmail shows it (specs/features/conversation-view.md). */
export type Conversation = {
  email: Email;
  count: number;
  isRead: boolean;
  messageIds: string[];
};

/** Emails grouped by thread, newest message representing each; unread if any message is. The
 *  list arrives newest first, so the first email seen for a thread is its newest. */
export function groupByThread(emails: readonly Email[]): Conversation[] {
  const byThread = new Map<string, Conversation>();
  for (const email of emails) {
    const key = email.threadId ?? email.id;
    const known = byThread.get(key);
    if (known === undefined) {
      byThread.set(key, { email, count: 1, isRead: email.isRead ?? false, messageIds: [email.id] });
      continue;
    }
    known.count += 1;
    known.isRead = known.isRead && (email.isRead ?? false);
    known.messageIds.push(email.id);
  }
  return [...byThread.values()];
}

/** The conversation around the open email: what came before it, and anything after. */
export function splitAround(
  messages: readonly ThreadMessage[],
  openedAt: string,
): { earlier: ThreadMessage[]; later: ThreadMessage[] } {
  const isEarlier = (message: ThreadMessage) =>
    message.timestamp == null || message.timestamp <= openedAt; // no date: assume it came first
  return { earlier: messages.filter(isEarlier), later: messages.filter((m) => !isEarlier(m)) };
}
