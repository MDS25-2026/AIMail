// Types only: client.ts imports this module, so a value import from it would be circular.
import type { RequestOptions } from "../lib/api/client";
import { ApiError, ApiErrorCode } from "../lib/api/errors";
import { Language } from "../lib/preferences";
import { en } from "../locales/en";
import { ms } from "../locales/ms";
import { zh } from "../locales/zh";
import {
  AuthStatus,
  type Email,
  type EmailPage,
  type Tone,
  type Translation,
} from "../types/email";
import type { SessionInfo } from "../types/session";
import { DEMO_ANSWERS, DEMO_CONFIRMED_DRAFTS } from "./data/answers";
import { DEMO_ACCOUNT, demoEmails } from "./data/emails";
import { leaveDemo } from "./mode";

/**
 * The demo's stand-in for the backend: every dashboard call is answered here, in memory, and
 * nothing leaves the page. Changes last until a reload, which starts the mailbox afresh.
 */

const NOT_IN_DEMO = 400;
const NOT_FOUND = 404;
const ANSWER_DELAY_MS = 150;
// The AI's prepared answers take a moment longer, so "Refining…" and the like can be read.
const THINKING_MS = 900;
const CONFIRMED_CONFIDENCE = 0.91;

let start = demoEmails(new Date());
let emails = structuredClone(start);

/** Back to the mailbox as it starts; for tests, as a reload does it in the app. */
export function resetDemo(now = new Date()) {
  start = demoEmails(now);
  emails = structuredClone(start);
}

type Json = Record<string, unknown>;
type Call = { params: string[]; json: Json; query: URLSearchParams; endpoint: string };
type Handler = (call: Call) => unknown;
type Method = "GET" | "POST" | "PUT" | "DELETE";
/** thinks: an AI action, answered after the model's usual pause. */
type Route = { method: Method; pattern: RegExp; handler: Handler; thinks?: boolean };

function find(id: string, endpoint: string): Email {
  const email = emails.find((candidate) => candidate.id === id);
  if (!email) throw new ApiError(NOT_FOUND, ApiErrorCode.NotFound, endpoint);
  return email;
}

/** Change one email in place and answer with it, as the backend's email actions do. */
function update({ params, endpoint }: Call, change: (email: Email) => Partial<Email>): Email {
  const email = find(params[0], endpoint);
  Object.assign(email, change(email));
  return email;
}

function notInDemo(endpoint: string): never {
  throw new ApiError(NOT_IN_DEMO, ApiErrorCode.NotInDemo, endpoint);
}

/** What a model call would add to the privacy receipt: the same details hidden as before. */
function aiSteps(email: Email, ...purposes: string[]): Email["egress"] {
  const earlier = email.egress?.[0];
  const added = purposes.map((purpose) => ({
    at: new Date().toISOString(),
    caught: earlier?.caught ?? 0,
    chars: email.draftReply.length,
    hidden: earlier?.hidden ?? {},
    provider: "gemini" as const,
    purpose,
  }));
  return [...(email.egress ?? []), ...added];
}

/** The draft in a tone: the email's own draft in its own tone, else the prepared one. */
function draftInTone({ params, endpoint }: Call, tone: Tone): string {
  const original = start.find((email) => email.id === params[0]);
  if (original?.tone === tone && original.draftReply) return original.draftReply;
  return DEMO_ANSWERS[params[0]]?.otherTone?.[tone] ?? notInDemo(endpoint);
}

// The refine suggestions, in every language the reader may have picked.
const SUGGESTED = {
  direct: new Set([en, ms, zh].map((locale) => locale.refine.suggestionDirect)),
  deadline: new Set([en, ms, zh].map((locale) => locale.refine.suggestionDeadline)),
};

/** A typed instruction has no prepared answer; only the suggestions under the box do. */
function refined({ params, endpoint, json }: Call): string {
  const instruction = String(json.instruction ?? "").trim();
  const answers = DEMO_ANSWERS[params[0]];
  if (SUGGESTED.direct.has(instruction)) return answers?.direct ?? notInDemo(endpoint);
  if (SUGGESTED.deadline.has(instruction)) return answers?.deadline ?? notInDemo(endpoint);
  throw new ApiError(NOT_IN_DEMO, ApiErrorCode.DemoSuggestionsOnly, endpoint);
}

function isLanguage(value: unknown): value is Language {
  return Object.values<unknown>(Language).includes(value);
}

const isDue = (until: string | null | undefined, now: Date) => !until || new Date(until) <= now;

const iso = (value: unknown) => new Date(String(value)).toISOString();

const session: SessionInfo = { email: DEMO_ACCOUNT, hasMailbox: true, needsReconnect: false };

const ROUTES: Route[] = [
  { method: "GET", pattern: /^\/auth\/session$/, handler: () => session },
  // Sign out in the account menu ends the demo, then the page goes to sign in as it always does.
  { method: "DELETE", pattern: /^\/auth\/session$/, handler: () => leaveDemo() },
  {
    method: "GET",
    pattern: /^\/emails$/,
    // Newest first, one page; a snoozed email stays out until its time comes, as on the backend.
    handler: (): EmailPage => ({
      emails: emails
        .filter((email) => isDue(email.snoozedUntil, new Date()))
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp)),
      nextCursor: null,
    }),
  },
  {
    method: "GET",
    pattern: /^\/emails\/by-thread\/([^/]+)$/,
    handler: ({ params, endpoint }) => {
      const email = emails.find((candidate) => candidate.threadId === params[0]);
      if (!email) throw new ApiError(NOT_FOUND, ApiErrorCode.NotFound, endpoint);
      return email;
    },
  },
  {
    method: "GET",
    pattern: /^\/emails\/([^/]+)$/,
    handler: (call) =>
      update(call, () => (call.query.get("markRead") === "false" ? {} : { isRead: true })),
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/unread$/,
    handler: (call) => void update(call, () => ({ isRead: false })),
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/send$/,
    // Pretend: the email is marked sent with the approved text, and nothing goes anywhere.
    handler: (call) =>
      update(call, () => ({
        draftReply: String(call.json.draft ?? ""),
        sentAt: new Date().toISOString(),
        scheduledFor: null,
        isRead: true,
        isAnswered: true,
      })),
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/schedule$/,
    handler: (call) =>
      update(call, () => ({
        draftReply: String(call.json.draft ?? ""),
        scheduledFor: iso(call.json.sendAt),
      })),
  },
  {
    method: "DELETE",
    pattern: /^\/emails\/([^/]+)\/schedule$/,
    handler: (call) => update(call, () => ({ scheduledFor: null })),
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/snooze$/,
    handler: (call) => update(call, () => ({ snoozedUntil: iso(call.json.until), isRead: false })),
  },
  {
    method: "DELETE",
    pattern: /^\/emails\/([^/]+)\/snooze$/,
    handler: (call) => update(call, () => ({ snoozedUntil: null })),
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/regenerate$/,
    thinks: true,
    handler: (call) => {
      const tone: Tone = call.json.tone === "casual" ? "casual" : "professional";
      const draftReply = draftInTone(call, tone);
      return update(call, (email) => ({
        tone,
        draftReply,
        egress: aiSteps({ ...email, draftReply }, "draft", "critic"),
      }));
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/refine$/,
    thinks: true,
    handler: (call) => {
      const draftReply = refined(call);
      return update(call, (email) => ({
        draftReply,
        egress: aiSteps({ ...email, draftReply }, "refine", "critic"),
      }));
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/translate$/,
    thinks: true,
    handler: ({ params, json, endpoint }): Translation => {
      const language = json.language;
      const text = isLanguage(language) ? DEMO_ANSWERS[params[0]]?.translations[language] : null;
      return { language: String(language), text: text ?? notInDemo(endpoint) };
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/confirm-sender$/,
    thinks: true,
    // The reader vouches for the sender, so drafting resumes, as on the backend.
    handler: (call) =>
      update(call, (email) => {
        const draftReply = DEMO_CONFIRMED_DRAFTS[email.id] ?? email.draftReply;
        return {
          authStatus: AuthStatus.SenderConfirmed,
          draftReply,
          criticConfidence: CONFIRMED_CONFIDENCE,
          egress: aiSteps({ ...email, draftReply }, "draft", "critic"),
        };
      }),
  },
];

function bodyOf(options: RequestOptions): Json {
  return (options.json ?? {}) as Json;
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** The demo's answer to a dashboard call; anything it does not cover is refused, never sent. */
export async function demoRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = String(options.method ?? "GET");
  const [pathname, search = ""] = path.split("?");
  const endpoint = `${method} ${pathname}`;
  for (const route of ROUTES) {
    const match = route.method === method ? route.pattern.exec(pathname) : null;
    if (!match) continue;
    // Answer after a network call's pause: the page shows its loading states, and the
    // server-rendered page hydrates before the answers land, as it does with the backend.
    await pause(ANSWER_DELAY_MS + (route.thinks ? THINKING_MS : 0));
    const answer = route.handler({
      params: match.slice(1).map(decodeURIComponent),
      json: bodyOf(options),
      query: new URLSearchParams(search),
      endpoint,
    });
    // A copy, so the page's cache never shares an object the demo goes on changing.
    return (answer === undefined ? undefined : structuredClone(answer)) as T;
  }
  await pause(ANSWER_DELAY_MS);
  return notInDemo(endpoint);
}
