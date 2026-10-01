import { describe, expect, test } from "vitest";

import { AdminApiError, isAuthError, retryUnlessAuth } from "../adminApi";

describe("admin retry policy", () => {
  test("a signed-out or forbidden answer is never retried", () => {
    expect(retryUnlessAuth(0, new AdminApiError(401, "admin_signed_out"))).toBe(false);
    expect(retryUnlessAuth(0, new AdminApiError(403, "not_an_admin"))).toBe(false);
  });

  test("a transient failure is retried, but not forever", () => {
    const outage = new AdminApiError(503, "supabase_unavailable");
    expect(retryUnlessAuth(0, outage)).toBe(true);
    expect(retryUnlessAuth(2, outage)).toBe(false);
  });

  test("only auth failures count as signed out", () => {
    expect(isAuthError(new AdminApiError(401, "x"))).toBe(true);
    expect(isAuthError(new Error("network"))).toBe(false);
  });
});
