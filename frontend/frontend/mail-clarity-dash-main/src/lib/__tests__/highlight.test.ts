import { describe, expect, test } from "vitest";

import { highlightUsed } from "../highlight";

const POLICY =
  "Refunds are processed within fourteen working days. Gifts above RM500 must be declared. " +
  "Staff may not accept hospitality from vendors during a tender.";

describe("source highlighting", () => {
  test("marks the sentence the draft draws on and only that one", () => {
    const draft = "Your refunds are processed within fourteen working days of approval.";
    const used = highlightUsed(POLICY, draft).filter((segment) => segment.isUsed);
    expect(used.map((segment) => segment.text)).toEqual([
      "Refunds are processed within fourteen working days.",
    ]);
  });

  test("common words alone never make a match", () => {
    const draft = "Please note that this would have been there with them.";
    expect(highlightUsed(POLICY, draft).some((segment) => segment.isUsed)).toBe(false);
  });

  test("keeps every sentence, in order, so the passage reads intact", () => {
    const joined = highlightUsed(POLICY, "")
      .map((segment) => segment.text)
      .join(" ");
    expect(joined).toBe(POLICY);
  });
});
