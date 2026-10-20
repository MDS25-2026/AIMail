// Types only: client.ts imports this module, so a value import from it would be circular.
import type { RequestOptions } from "../lib/api/client";
import { ApiError, ApiErrorCode } from "../lib/api/errors";
import { Language } from "../lib/preferences";
import {
  AuthStatus,
  type Email,
  type EmailPage,
  type Tone,
  type Translation,
} from "../types/email";
import type { SessionInfo } from "../types/session";
import { COMPOSE_ROUTES } from "./compose";
import { DEMO_ANSWERS, DEMO_CONFIRMED_DRAFTS } from "./data/answers";
import { DEMO_ACCOUNT } from "./data/emails";
import { leaveDemo } from "./mode";
import { PAGE_ROUTES } from "./pages";
import {
  notFound,
  notInDemo,
  record,
  state,
  SUGGESTED,
  updateEmail,
  type Call,
  type Json,
  type Route,
} from "./state";

/**
 * The demo's stand-in for the backend: every dashboard call is answered here, in memory, and
 * nothing leaves the page. Changes last until a reload, which starts the mailbox afresh.
 */

const NOT_IN_DEMO = 400;
const ANSWER_DELAY_MS = 150;
// The AI's prepared answers take a moment longer, so "Refining…" and the like can be read.
const THINKING_MS = 900;
const CONFIRMED_CONFIDENCE = 0.91;

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
  const original = state.start.find((email) => email.id === params[0]);
  if (original?.tone === tone && original.draftReply) return original.draftReply;
  return DEMO_ANSWERS[params[0]]?.otherTone?.[tone] ?? notInDemo(endpoint);
}

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

const EMAIL_ROUTES: Route[] = [
  { method: "GET", pattern: /^\/auth\/session$/, handler: () => session },
  // Sign out in the account menu ends the demo, then the page goes to sign in as it always does.
  { method: "DELETE", pattern: /^\/auth\/session$/, handler: () => leaveDemo() },
  {
    method: "GET",
    pattern: /^\/emails$/,
    // Newest first, one page; a snoozed email stays out until its time comes, as on the backend.
    handler: (): EmailPage => ({
      emails: state.emails
        .filter((email) => isDue(email.snoozedUntil, new Date()))
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp)),
      nextCursor: null,
    }),
  },
  {
    method: "GET",
    pattern: /^\/emails\/by-thread\/([^/]+)$/,
    handler: ({ params, endpoint }) =>
      state.emails.find((email) => email.threadId === params[0]) ?? notFound(endpoint),
  },
  {
    method: "GET",
    pattern: /^\/emails\/([^/]+)$/,
    handler: (call) =>
      updateEmail(call, () => (call.query.get("markRead") === "false" ? {} : { isRead: true })),
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/unread$/,
    handler: (call) => void updateEmail(call, () => ({ isRead: false })),
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/send$/,
    // Pretend: the email is marked sent with the approved text, and nothing goes anywhere.
    handler: (call) => {
      const email = updateEmail(call, () => ({
        draftReply: String(call.json.draft ?? ""),
        sentAt: new Date().toISOString(),
        scheduledFor: null,
        isRead: true,
        isAnswered: true,
      }));
      record("approve_and_send", { message: email.id, restored: email.details?.length ?? 0 });
      return email;
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/schedule$/,
    handler: (call) => {
      const email = updateEmail(call, () => ({
        draftReply: String(call.json.draft ?? ""),
        scheduledFor: iso(call.json.sendAt),
      }));
      record("send_scheduled", { message: email.id });
      return email;
    },
  },
  {
    method: "DELETE",
    pattern: /^\/emails\/([^/]+)\/schedule$/,
    handler: (call) => {
      const email = updateEmail(call, () => ({ scheduledFor: null }));
      record("scheduled_send_cancelled", { message: email.id, reason: "cancelled" });
      return email;
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/snooze$/,
    handler: (call) => {
      const email = updateEmail(call, () => ({
        snoozedUntil: iso(call.json.until),
        isRead: false,
      }));
      record("email_snoozed", { message: email.id, snoozed: true });
      return email;
    },
  },
  {
    method: "DELETE",
    pattern: /^\/emails\/([^/]+)\/snooze$/,
    handler: (call) => {
      const email = updateEmail(call, () => ({ snoozedUntil: null }));
      record("email_snoozed", { message: email.id, snoozed: false });
      return email;
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/regenerate$/,
    thinks: true,
    handler: (call) => {
      const tone: Tone = call.json.tone === "casual" ? "casual" : "professional";
      const draftReply = draftInTone(call, tone);
      const email = updateEmail(call, (current) => ({
        tone,
        draftReply,
        egress: aiSteps({ ...current, draftReply }, "draft", "critic"),
      }));
      const fields = { message: email.id, tone, confidence: email.criticConfidence };
      record("generate_draft", { ...fields, review: (email.reviewReasons?.length ?? 0) > 0 });
      return email;
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/refine$/,
    thinks: true,
    handler: (call) => {
      const draftReply = refined(call);
      const email = updateEmail(call, (current) => ({
        draftReply,
        egress: aiSteps({ ...current, draftReply }, "refine", "critic"),
      }));
      record("refine_draft", {
        message: email.id,
        review: (email.reviewReasons?.length ?? 0) > 0,
      });
      return email;
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/translate$/,
    thinks: true,
    handler: ({ params, json, endpoint }): Translation => {
      const language = json.language;
      const text = isLanguage(language) ? DEMO_ANSWERS[params[0]]?.translations[language] : null;
      if (!text) return notInDemo(endpoint);
      record("translate_email", { message: params[0], language: String(language) });
      return { language: String(language), text };
    },
  },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/confirm-sender$/,
    thinks: true,
    // The reader vouches for the sender, so drafting resumes, as on the backend.
    handler: (call) => {
      const email = updateEmail(call, (current) => {
        const draftReply = DEMO_CONFIRMED_DRAFTS[current.id] ?? current.draftReply;
        return {
          authStatus: AuthStatus.SenderConfirmed,
          draftReply,
          criticConfidence: CONFIRMED_CONFIDENCE,
          egress: aiSteps({ ...current, draftReply }, "draft", "critic"),
        };
      });
      record("confirm_sender", { message: email.id });
      return email;
    },
  },
];

const ROUTES = [...EMAIL_ROUTES, ...PAGE_ROUTES, ...COMPOSE_ROUTES];

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
    const answer = await route.handler({
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
