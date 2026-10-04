import { afterEach, describe, expect, test, vi } from "vitest";

import { SignedOutError, fetchEmails, sendEmail } from "../api";

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
    recordFetch(401, { detail: "signed_out" });
    await expect(fetchEmails()).rejects.toBeInstanceOf(SignedOutError);
  });
});
