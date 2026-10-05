/**
 * Runs inside Gmail. Reads only which conversation is open (one attribute and the URL), never any
 * email content, and tells the AIMail side panel when it changes.
 */
import { threadIdFromPage } from "./gmailThread";
import { isWhichThread, MessageType, type ThreadReport } from "./messages";

// Gmail re-renders constantly; one look after it settles is enough.
const SETTLE_MS = 300;

let reported: string | null | undefined;
let pending: number | undefined;

function isVisible(element: Element): boolean {
  return element.getClientRects().length > 0;
}

function currentThread(): string | null {
  return threadIdFromPage(document, location.href, isVisible);
}

function report(): void {
  pending = undefined;
  const threadId = currentThread();
  if (threadId === reported) return;
  reported = threadId;
  const message: ThreadReport = { type: MessageType.ThreadChanged, threadId };
  // No panel open means nobody is listening, which is normal.
  chrome.runtime.sendMessage(message).catch(() => undefined);
}

function schedule(): void {
  if (pending !== undefined) window.clearTimeout(pending);
  pending = window.setTimeout(report, SETTLE_MS);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!isWhichThread(message)) return undefined;
  const reply: ThreadReport = { type: MessageType.ThreadChanged, threadId: currentThread() };
  sendResponse(reply);
  return undefined;
});

window.addEventListener("hashchange", schedule);
new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
schedule();
