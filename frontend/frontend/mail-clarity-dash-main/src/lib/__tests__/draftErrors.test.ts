import { afterEach, describe, expect, test, vi } from "vitest";

import {
  DraftRefusedError,
  GoogleAccessExpiredError,
  SendOutcomeUnknownError,
  regenerateEmail,
  sendEmail,
} from "../api";

function answer(status: number, body: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("regenerate failures", () => {
  test("a draft the model refused is its own error, since retrying cannot help", async () => {
    answer(422, JSON.stringify({ detail: "draft_refused" }));
    await expect(regenerateEmail("id", "casual")).rejects.toBeInstanceOf(DraftRefusedError);
  });

  test("an unavailable agent stays an ordinary error, since retrying later can help", async () => {
    answer(502, JSON.stringify({ detail: "agent_unavailable" }));
    const failure = regenerateEmail("id", "casual");
    await expect(failure).rejects.toThrow("failed (502)");
    await expect(failure).rejects.not.toBeInstanceOf(DraftRefusedError);
  });

  test("a body that is not JSON is still an ordinary error", async () => {
    answer(500, "Internal Server Error");
    await expect(regenerateEmail("id", "casual")).rejects.not.toBeInstanceOf(DraftRefusedError);
  });
});

describe("send failures", () => {
  test("a send whose outcome is unknown is its own error, so the reader checks Gmail before retrying", async () => {
    answer(504, JSON.stringify({ detail: "send_outcome_unknown" }));
    await expect(sendEmail("id", "Thanks.")).rejects.toBeInstanceOf(SendOutcomeUnknownError);
  });

  test("a refused send stays an ordinary error", async () => {
    answer(502, JSON.stringify({ detail: "send_failed" }));
    await expect(sendEmail("id", "Thanks.")).rejects.not.toBeInstanceOf(SendOutcomeUnknownError);
  });
});

describe("expired Google access", () => {
  test("a send Google refused for expired access says to sign in again, not to retry", async () => {
    answer(409, JSON.stringify({ detail: "google_access_expired" }));
    await expect(sendEmail("id", "Hi")).rejects.toBeInstanceOf(GoogleAccessExpiredError);
  });
});
