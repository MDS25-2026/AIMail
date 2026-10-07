import { afterEach, describe, expect, test, vi } from "vitest";

import { addStyleExample, saveStyleDescription, WritingStyleError } from "../api";

function answer(status: number, body: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("writing style failures", () => {
  test("a masker that is down comes back as its own code, so the card can say nothing was saved", async () => {
    answer(503, JSON.stringify({ detail: "masking_unavailable" }));
    await expect(saveStyleDescription("Warm")).rejects.toMatchObject({
      code: "masking_unavailable",
    });
  });

  test("a full set of examples is reported by code", async () => {
    answer(409, JSON.stringify({ detail: "too_many_examples" }));
    await expect(addStyleExample({ text: "Hi" })).rejects.toMatchObject({
      code: "too_many_examples",
    });
  });

  test("a body that is not JSON still fails as a writing style error", async () => {
    answer(500, "Internal Server Error");
    await expect(addStyleExample({ emailId: "e1" })).rejects.toBeInstanceOf(WritingStyleError);
  });
});
