import type { Email, EmailCategory, Priority } from "../types/email";
import { groupByThread, type Conversation } from "./conversations";

// A Record rather than a list, so a new tier in Priority fails to compile until it is placed here.
const RANK: Record<Priority, number> = { critical: 0, high: 1, medium: 2, low: 3 };

/** Every priority, most urgent first: the order the filter offers them in. */
export const PRIORITIES = (Object.keys(RANK) as Priority[]).sort((a, b) => RANK[a] - RANK[b]);

export type PriorityFilter = Priority | "all";

/** The conversations to list. A row shows its newest email, so that email's priority decides,
 *  matching the badge the reader sees on the row. */
export function filterByPriority(
  conversations: Conversation[],
  filter: PriorityFilter,
): Conversation[] {
  if (filter === "all") return conversations;
  return conversations.filter(({ email }) => email.priority === filter);
}

/** Primary: mail from people. Updates: newsletters and notifications, the listener's automated flag
 *  (specs/features/inbox-updates-tab.md). */
export type InboxView = "primary" | "updates";

export const INBOX_VIEWS: readonly InboxView[] = ["primary", "updates"];

export const viewOf = (email: Email): InboxView => (email.isAutomated ? "updates" : "primary");

/** The conversations in one view, decided by the row's email like the filters. */
export function filterByView(conversations: Conversation[], view: InboxView): Conversation[] {
  return conversations.filter(({ email }) => viewOf(email) === view);
}

/** Of the loaded pages only: older pages may hold more. */
export const unreadCount = (conversations: Conversation[]) =>
  conversations.filter(({ isRead }) => !isRead).length;

/** The tab an email is listed under: its conversation's, so an older newsletter answered by a
 *  person is in Primary with the reply. Not loaded yet: its own flag is all there is to go on. */
export function tabOf(emails: readonly Email[], email: Email): InboxView {
  const conversation = groupByThread(emails).find(({ messageIds }) =>
    messageIds.includes(email.id),
  );
  return viewOf(conversation?.email ?? email);
}

/** The email a desktop opens beside a tab: its newest conversation's, the row it is listed by. */
export function firstEmailIn(emails: readonly Email[], view: InboxView): string | null {
  return filterByView(groupByThread(emails), view)[0]?.email.id ?? null;
}

export type InboxSort = "urgent" | "newest";

/** "urgent": most urgent first, by the row's email like the filter (#142). The list arrives newest
 *  first and the sort is stable, so each tier stays newest first. */
export function sortConversations(conversations: Conversation[], sort: InboxSort): Conversation[] {
  if (sort === "newest") return conversations;
  return [...conversations].sort((a, b) => RANK[a.email.priority] - RANK[b.email.priority]);
}

// Same trick as RANK: a new category fails to compile until it has a place in the filter.
const CATEGORY_ORDER: Record<EmailCategory, number> = {
  client: 0,
  vendor: 1,
  internal: 2,
  security: 3,
  admin: 4,
  personal: 5,
};

/** The six categories, in the taxonomy's order. */
export const CATEGORIES = (Object.keys(CATEGORY_ORDER) as EmailCategory[]).sort(
  (a, b) => CATEGORY_ORDER[a] - CATEGORY_ORDER[b],
);

/** Below this the classifier is unsure, so no category is shown rather than a likely-wrong one. */
export const CATEGORY_MIN_CONFIDENCE = 0.5;

/**
 * The category to show, or null. The API sends `internal` with no confidence for an email the
 * worker has not classified yet (#186), so a missing confidence means "not classified", never
 * "internal".
 */
export function shownCategory(email: Email): EmailCategory | null {
  const confidence = email.categoryConfidence;
  if (confidence === null || confidence === undefined) return null;
  return confidence >= CATEGORY_MIN_CONFIDENCE ? email.category : null;
}

export type CategoryFilter = EmailCategory | "all";

/** Rows whose shown category matches; unclassified rows appear under "all" only. */
export function filterByCategory(
  conversations: Conversation[],
  filter: CategoryFilter,
): Conversation[] {
  if (filter === "all") return conversations;
  return conversations.filter(({ email }) => shownCategory(email) === filter);
}
