import { describe, expect, test } from "vitest";

import { MAX_TEMPLATE_TRIGGERS, parseTriggers } from "../templates";

describe("trigger words", () => {
  test("are split on commas, Chinese commas included, trimmed, and blanks dropped", () => {
    expect(parseTriggers(" invoice, bayar ,，发票,")).toEqual(["invoice", "bayar", "发票"]);
  });

  test("stop at the backend's limit", () => {
    expect(parseTriggers(Array.from({ length: 15 }, (_, i) => `w${i}`).join(","))).toHaveLength(
      MAX_TEMPLATE_TRIGGERS,
    );
  });
});
