import type { Priority } from "../types/email";
import type { Conversation } from "./conversations";

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
