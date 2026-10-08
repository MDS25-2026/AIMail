import { afterEach, describe, expect, test, vi } from "vitest";

import { fetchAdminSession, isAuthError, retryUnlessAuth } from "../adminApi";
import { ApiError, ApiErrorCode, isSignedOut } from "../api/errors";
import { createQueryClient } from "../queries";

afterEach(() => vi.unstubAllGlobals());

function answer(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status })),
  );
}

async function failureOf(call: () => Promise<unknown>): Promise<unknown> {
  return call().then(
    () => null,
    (error: unknown) => error,
  );
}

describe("admin retry policy", () => {
  test("a signed-out or forbidden answer is never retried", () => {
    expect(
      retryUnlessAuth(0, new ApiError(401, ApiErrorCode.AdminSignedOut, "GET /admin/session")),
    ).toBe(false);
    expect(
      retryUnlessAuth(0, new ApiError(403, ApiErrorCode.NotAnAdmin, "GET /admin/session")),
    ).toBe(false);
  });

  test("a transient failure is retried, but not forever", () => {
    const outage = new ApiError(503, ApiErrorCode.SupabaseUnavailable, "GET /admin/overview");
    expect(retryUnlessAuth(0, outage)).toBe(true);
    expect(retryUnlessAuth(2, outage)).toBe(false);
  });

  test("only auth failures count as signed out", () => {
    expect(isAuthError(new ApiError(401, ApiErrorCode.Unknown, "GET /admin/session"))).toBe(true);
    expect(isAuthError(new Error("network"))).toBe(false);
  });
});

describe("signed out of the console", () => {
  test.each([
    { detail: "admin_signed_out" },
    { error: { code: "admin_signed_out", message: "no admin session" } },
    {},
  ])("is an admin sign-out, never the reader's own (%j)", async (body) => {
    answer(401, body);
    const error = await failureOf(fetchAdminSession);
    expect(isAuthError(error)).toBe(true);
    expect(isSignedOut(error)).toBe(false);
  });

  test("does not send the reader to the dashboard sign-in", async () => {
    answer(401, { detail: "admin_signed_out" });
    const onSignedOut = vi.fn();
    const client = createQueryClient({ onSignedOut });
    await client
      .fetchQuery({ queryKey: ["admin", "session"], queryFn: fetchAdminSession, retry: false })
      .catch(() => undefined);
    expect(onSignedOut).not.toHaveBeenCalled();
  });
});
