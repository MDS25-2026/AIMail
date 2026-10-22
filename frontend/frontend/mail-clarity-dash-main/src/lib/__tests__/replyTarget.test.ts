import { describe, expect, test } from "vitest";

import { replyGoesElsewhere } from "../replyTarget";

describe("where an approved reply goes (security review, 2026-10-21)", () => {
  test("no warning when the reply goes back to the sender", () => {
    expect(replyGoesElsewhere("Boss <boss@corp.example>", null)).toBeNull();
    expect(replyGoesElsewhere("Boss <boss@corp.example>", "BOSS@corp.example")).toBeNull();
  });

  test("names the address when a Reply-To sends it somewhere else", () => {
    expect(replyGoesElsewhere("boss@corp.example", "Help <help@other.example>")).toBe(
      "help@other.example",
    );
  });

  test("no warning for a Reply-To listing several, which the backend ignores", () => {
    expect(
      replyGoesElsewhere("boss@corp.example", "boss@corp.example, thief@evil.example"),
    ).toBeNull();
  });
});
