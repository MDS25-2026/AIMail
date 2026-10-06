/** What the Gmail content script and the side panel say to each other. */
export enum MessageType {
  ThreadChanged = "aimail:thread-changed",
  WhichThread = "aimail:which-thread",
}

/** The thread Gmail has open, or null on a list view. */
export type ThreadReport = { type: MessageType.ThreadChanged; threadId: string | null };

export type WhichThread = { type: MessageType.WhichThread };

function hasType(value: unknown, type: MessageType): value is { type: MessageType } {
  return typeof value === "object" && value !== null && "type" in value && value.type === type;
}

export function isThreadReport(value: unknown): value is ThreadReport {
  if (!hasType(value, MessageType.ThreadChanged) || !("threadId" in value)) return false;
  return value.threadId === null || typeof value.threadId === "string";
}

export function isWhichThread(value: unknown): value is WhichThread {
  return hasType(value, MessageType.WhichThread);
}
