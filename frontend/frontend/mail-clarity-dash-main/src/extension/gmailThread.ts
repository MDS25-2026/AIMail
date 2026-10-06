/**
 * Which Gmail conversation is open, as the hex thread id the Gmail API (and messages.thread_id)
 * uses. Gmail's URL carries a different, encoded id, so the page's own attributes come first.
 */

const GMAIL_ORIGIN = "https://mail.google.com/";
const HEX_THREAD_ID = /^[0-9a-f]{12,20}$/;
// The last URL segment of an open conversation is a long opaque id; a list view ends in a label
// or a page marker ("#inbox", "#inbox/p2").
const CONVERSATION_SEGMENT = /^[A-Za-z0-9]{16,}$/;
const PERM_ID = /^thread-f:(\d+)$/;

export function isGmailUrl(url: string | undefined): boolean {
  return url?.startsWith(GMAIL_ORIGIN) ?? false;
}

export function isConversationUrl(url: string): boolean {
  const hash = new URL(url).hash.slice(1);
  const segments = hash.split("/");
  return segments.length > 1 && CONVERSATION_SEGMENT.test(segments[segments.length - 1] ?? "");
}

/** "thread-f:1779..." (decimal) to the API's hex form. */
export function hexFromPermId(permId: string): string | null {
  const match = PERM_ID.exec(permId);
  if (!match?.[1]) return null;
  return BigInt(match[1]).toString(16);
}

/** Older Gmail URLs end in the hex id itself. */
export function threadIdFromUrl(url: string): string | null {
  const last = new URL(url).hash.split("/").pop() ?? "";
  return HEX_THREAD_ID.test(last) ? last : null;
}

/** The slice of the DOM this reads, so it runs against Gmail's page and against test fixtures. */
type Tagged = { getAttribute(name: string): string | null };
type Page<T extends Tagged> = { querySelectorAll(selector: string): Iterable<T> };

function firstVisible<T extends Tagged>(
  page: Page<T>,
  attribute: string,
  isVisible: (element: T) => boolean,
): string | null {
  const element = [...page.querySelectorAll(`[${attribute}]`)].find(isVisible);
  return element?.getAttribute(attribute) ?? null;
}

/**
 * The open thread's id, or null when no conversation is open. Gmail keeps earlier conversations
 * in the page, hidden, so only a visible one counts.
 */
export function threadIdFromPage<T extends Tagged>(
  page: Page<T>,
  url: string,
  isVisible: (element: T) => boolean,
): string | null {
  if (!isConversationUrl(url)) return null;
  const legacy = firstVisible(page, "data-legacy-thread-id", isVisible);
  if (legacy && HEX_THREAD_ID.test(legacy)) return legacy;
  const perm = firstVisible(page, "data-thread-perm-id", isVisible);
  return (perm && hexFromPermId(perm)) || threadIdFromUrl(url);
}
