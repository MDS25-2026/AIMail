import { describe, expect, test } from "vitest";

import { isAuthError, retryUnlessAuth } from "../adminApi";
import { ApiError, ApiErrorCode } from "../api/errors";

describe("admin retry policy", () => {
  test("a signed-out or forbidden answer is never retried", () => {
    expect(
      retryUnlessAuth(0, new ApiError(401, ApiErrorCode.SignedOut, "GET /admin/session")),
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
