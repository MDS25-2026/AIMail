// Types only: client.ts imports this module, so a value import from it would be circular.
import type { RequestOptions } from "../lib/api/client";
import { ApiError, ApiErrorCode } from "../lib/api/errors";
import type { Email, EmailPage } from "../types/email";
import type { SessionInfo } from "../types/session";
import { DEMO_ACCOUNT, demoEmails } from "./data/emails";
import { leaveDemo } from "./mode";

/**
 * The demo's stand-in for the backend: every dashboard call is answered here, in memory, and
 * nothing leaves the page. Changes last until a reload, which starts the mailbox afresh.
 */

const NOT_IN_DEMO = 400;
const NOT_FOUND = 404;
const ANSWER_DELAY_MS = 150;

let emails = demoEmails(new Date());

/** Back to the mailbox as it starts; for tests, as a reload does it in the app. */
export function resetDemo(now = new Date()) {
  emails = demoEmails(now);
}

type Json = Record<string, unknown>;
type Call = { params: string[]; json: Json; query: URLSearchParams; endpoint: string };
type Handler = (call: Call) => unknown;
type Method = "GET" | "POST" | "PUT" | "DELETE";
type Route = { method: Method; pattern: RegExp; handler: Handler };

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
];

function bodyOf(options: RequestOptions): Json {
  return (options.json ?? {}) as Json;
}

/** The demo's answer to a dashboard call; anything it does not cover is refused, never sent. */
export async function demoRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = String(options.method ?? "GET");
  const [pathname, search = ""] = path.split("?");
  const endpoint = `${method} ${pathname}`;
  // Answer after a network call's pause: the page shows its loading states, and the server-rendered
  // page hydrates before the answers land, as it does with the backend.
  await new Promise((resolve) => setTimeout(resolve, ANSWER_DELAY_MS));
  for (const route of ROUTES) {
    const match = route.method === method ? route.pattern.exec(pathname) : null;
    if (!match) continue;
    const params = match.slice(1).map(decodeURIComponent);
    const answer = route.handler({
      params,
      json: bodyOf(options),
      query: new URLSearchParams(search),
      endpoint,
    });
    // A copy, so the page's cache never shares an object the demo goes on changing.
    return (answer === undefined ? undefined : structuredClone(answer)) as T;
  }
  throw new ApiError(NOT_IN_DEMO, ApiErrorCode.NotInDemo, endpoint);
}
