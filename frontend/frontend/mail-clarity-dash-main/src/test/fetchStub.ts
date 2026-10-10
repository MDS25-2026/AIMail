import { vi } from "vitest";

/** A canned backend answer; a promise lets a test decide when it lands. */
export type StubReply = { status?: number; body?: unknown };
type Handler = StubReply | ((call: StubCall) => StubReply | Promise<StubReply>);
export type StubCall = { method: string; path: string; body: unknown };

const OK = 200;
const NOT_FOUND = 404;

function parse(init: RequestInit | undefined): unknown {
  return typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
}

function toResponse({ status = OK, body }: StubReply): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), { status });
}

/** Stubs fetch by "METHOD /path"; an unrouted call answers 404, so a missing route fails loudly. */
export function stubFetch(routes: Record<string, Handler>): StubCall[] {
  const calls: StubCall[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const call = {
        method: init?.method ?? "GET",
        path: new URL(url).pathname,
        body: parse(init),
      };
      calls.push(call);
      const handler = routes[`${call.method} ${call.path}`];
      if (handler === undefined) {
        return toResponse({ status: NOT_FOUND, body: { error: { code: "not_found" } } });
      }
      return toResponse(typeof handler === "function" ? await handler(call) : handler);
    }),
  );
  return calls;
}

/** A promise with its resolve exposed, to hold a response back until the test releases it. */
export function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

/** The calls that change something: "nothing was sent" means none of these, whatever was read. */
export function writes(calls: StubCall[]): StubCall[] {
  return calls.filter((call) => call.method !== "GET");
}
