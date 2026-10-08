import { afterEach, describe, expect, test, vi } from "vitest";

import { fetchEmails, sendEmail } from "../api/emails";
import { ApiErrorCode } from "../api/errors";

function recordFetch(status: number, body: unknown = []) {
  const calls: { url: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      return new Response(JSON.stringify(body), { status });
    }),
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("calls to the backend (ADR 0005)", () => {
  test("carry the session cookie and the client header, never a token", async () => {
    const calls = recordFetch(200);
    await fetchEmails();
    const { init } = calls[0];
    expect(init.credentials).toBe("include");
    expect(init.headers).toMatchObject({ "X-AIMail-Client": "1" });
    expect(JSON.stringify(init.headers)).not.toContain("Authorization");
  });

  test("a write keeps its own headers alongside the client header", async () => {
    const calls = recordFetch(200, {});
    await sendEmail("id", "Thanks.");
    expect(calls[0].init.headers).toMatchObject({
      "Content-Type": "application/json",
      "X-AIMail-Client": "1",
    });
  });

  test("a 401 means signed out, so the app can send the reader to sign in", async () => {
    recordFetch(401, { error: { code: "signed_out", message: "no session" } });
    await expect(fetchEmails()).rejects.toMatchObject({ code: ApiErrorCode.SignedOut });
  });
});

/** Answers each call with the next status in turn, recording the paths asked for. */
function answerInTurn(...statuses: number[]) {
  const paths: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      paths.push(new URL(url).pathname);
      const status = statuses.shift() ?? 200;
      // A 204 may not carry a body.
      return new Response(status === 204 ? null : JSON.stringify([]), { status });
    }),
  );
  return paths;
}

describe("staying signed in", () => {
  test("an expired session is renewed from the refresh cookie and the call retried", async () => {
    const paths = answerInTurn(401, 204, 200);
    await expect(fetchEmails()).resolves.toEqual([]);
    expect(paths).toEqual(["/emails", "/auth/session/refresh", "/emails"]);
  });

  test("when the renewal is refused too, the reader is signed out, without looping", async () => {
    const paths = answerInTurn(401, 401);
    await expect(fetchEmails()).rejects.toMatchObject({ code: ApiErrorCode.SignedOut });
    expect(paths).toEqual(["/emails", "/auth/session/refresh"]);
  });

  test("calls that expire together share one renewal, since a refresh token works only once", async () => {
    const paths = answerInTurn(401, 401, 204, 200, 200);
    await Promise.all([fetchEmails(), fetchEmails()]);
    expect(paths.filter((path) => path === "/auth/session/refresh")).toHaveLength(1);
  });
});
