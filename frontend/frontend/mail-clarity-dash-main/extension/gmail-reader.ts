import type { Email, Priority, Tone, ThreadMessage } from "../src/components/extension/types";

/**
 * Reads the currently open Gmail conversation straight from the page DOM.
 * Gmail ships obfuscated class names, but a handful of them have been stable
 * for years and are what every Gmail extension keys off:
 *   h2.hP        conversation subject
 *   div.adn.ads  one expanded message in the thread
 *   span.gD      sender name (with an `email` attribute)
 *   div.a3s      message body
 *   span.g3[title] absolute timestamp
 * If any of it changes, readGmailThread() returns null and the panel falls
 * back to mock data instead of crashing.
 */

const SUBJECT = "h2.hP";
const MESSAGE = "div.adn.ads";
const SENDER = "span.gD";
const BODY = "div.a3s";
const TIME = "span.g3[title], span.gK span[title]";

function text(el: Element | null | undefined): string {
  return (el?.textContent ?? "").replace(/\u200c/g, "").trim();
}

function bodyText(el: Element | null | undefined): string {
  if (!el) return "";
  const clone = el.cloneNode(true) as HTMLElement;
  clone.querySelectorAll(".gmail_quote, blockquote, style, script").forEach((n) => n.remove());
  return (clone.innerText ?? clone.textContent ?? "")
    .replace(/\u200c/g, "")
    .split("\n")
    .map((line) => line.trimEnd())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function parseTimestamp(el: Element | null | undefined): string {
  const title = el?.getAttribute("title");
  if (title) {
    const parsed = new Date(title);
    if (!Number.isNaN(parsed.getTime())) return parsed.toISOString();
  }
  return new Date().toISOString();
}

const URGENT_WORDS = ["urgent", "asap", "today", "eod", "deadline", "by friday", "immediately"];
const SOON_WORDS = ["tomorrow", "this week", "reminder", "follow up", "waiting", "blocked"];

function derivePriority(subject: string, body: string): Priority {
  const haystack = `${subject}\n${body}`.toLowerCase();
  if (URGENT_WORDS.some((w) => haystack.includes(w))) return "high";
  if (SOON_WORDS.some((w) => haystack.includes(w))) return "medium";
  return "low";
}

function sentences(body: string): string[] {
  return body
    .replace(/\s+/g, " ")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 20);
}

function deriveSummary(sender: string, body: string): string {
  const first = sentences(body).slice(0, 2).join(" ");
  if (!first) return `${sender} sent a short message with no extractable detail.`;
  return `${sender}: ${first.length > 260 ? `${first.slice(0, 257)}...` : first}`;
}

function deriveActionItems(body: string): string[] {
  const asks = sentences(body).filter((s) =>
    /\?|\b(can you|could you|please|need|needs|send|confirm|review|let me know|by \w+day)\b/i.test(
      s,
    ),
  );
  const items = asks.slice(0, 3).map((s) => (s.length > 120 ? `${s.slice(0, 117)}...` : s));
  return items.length > 0 ? items : ["Read the thread and decide on a reply"];
}

function firstName(sender: string): string {
  return sender.split(/[\s<]/)[0] || "there";
}

function deriveDraft(sender: string, body: string): string {
  const asks = deriveActionItems(body);
  const lines = [
    `Hi ${firstName(sender)},`,
    "",
    "Thanks for the note — I've read through the thread.",
    asks[0] ? `On "${asks[0]}": I'll take care of it and follow up shortly.` : "",
    "",
    "Best,",
  ].filter(Boolean);
  return lines.join("\n");
}

function deriveTone(body: string): Tone {
  return /\b(hey|hi there|thanks!|cheers|😊|!)/i.test(body) ? "casual" : "professional";
}

function maskedPii(body: string): boolean {
  return /\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b|\b\d{13,16}\b|\+?\d[\d\s().-]{8,}\d/.test(body);
}

/** Returns the open Gmail conversation as an Email, or null if none is open. */
export function readGmailThread(): Email | null {
  const main = document.querySelector('div[role="main"]');
  if (!main) return null;

  const subjectEl = main.querySelector(SUBJECT);
  const messageEls = Array.from(main.querySelectorAll(MESSAGE));
  if (!subjectEl || messageEls.length === 0) return null;

  const subject = text(subjectEl) || "(no subject)";

  const parsed = messageEls.map((el) => {
    const senderEl = el.querySelector(SENDER);
    const sender =
      text(senderEl) || senderEl?.getAttribute("email") || senderEl?.getAttribute("name") || "Unknown sender";
    return {
      sender,
      body: bodyText(el.querySelector(BODY)),
      timestamp: parseTimestamp(el.querySelector(TIME)),
    };
  });

  const latest = parsed[parsed.length - 1];
  if (!latest.body) return null;

  const threadContext: ThreadMessage[] = parsed.slice(0, -1).map((m) => ({
    sender: m.sender,
    snippet: m.body.replace(/\s+/g, " ").slice(0, 140),
  }));

  const id = `gmail_${location.hash.split("/").pop() || parsed.length}_${subject.slice(0, 24)}`;

  return {
    id,
    sender: latest.sender,
    subject,
    preview: latest.body.replace(/\s+/g, " ").slice(0, 160),
    timestamp: latest.timestamp,
    priority: derivePriority(subject, latest.body),
    originalBody: latest.body,
    threadContext,
    aiSummary: deriveSummary(latest.sender, latest.body),
    actionItems: deriveActionItems(latest.body),
    draftReply: deriveDraft(latest.sender, latest.body),
    tone: deriveTone(latest.body),
    sources: [
      { label: `Thread messages (${parsed.length})` },
      { label: "Gmail: open conversation" },
    ],
    piiMasked: maskedPii(latest.body),
    criticConfidence: Math.min(0.95, 0.6 + Math.min(latest.body.length, 1200) / 4000),
  };
}

/**
 * Calls back whenever the open conversation changes. Gmail is a SPA, so we
 * watch both the hash route and DOM mutations, debounced so a burst of Gmail
 * re-renders results in one read.
 */
export function observeGmailThread(onChange: (email: Email | null) => void): () => void {
  let lastKey = "";
  let timer: number | undefined;

  const read = () => {
    const email = readGmailThread();
    const key = email ? `${email.id}|${email.originalBody.length}` : "none";
    if (key === lastKey) return;
    lastKey = key;
    onChange(email);
  };

  const schedule = () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(read, 300);
  };

  const observer = new MutationObserver(schedule);
  observer.observe(document.body, { childList: true, subtree: true });
  window.addEventListener("hashchange", schedule);
  schedule();

  return () => {
    observer.disconnect();
    window.removeEventListener("hashchange", schedule);
    window.clearTimeout(timer);
  };
}
