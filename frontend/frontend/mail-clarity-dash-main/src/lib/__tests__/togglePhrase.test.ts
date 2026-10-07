import { describe, expect, test } from "vitest";

import { MAX_DESCRIPTION_CHARS, togglePhrase } from "../writingStyle";

describe("quick picks", () => {
  test("a pick adds its phrase after what the user typed", () => {
    expect(togglePhrase("Warm but brief.", "Always thank the sender first.")).toBe(
      "Warm but brief. Always thank the sender first.",
    );
  });

  test("picking it again takes the phrase out and leaves the rest", () => {
    const text = "Warm. Always thank the sender first. No jargon.";
    expect(togglePhrase(text, "Always thank the sender first.")).toBe("Warm. No jargon.");
  });

  test("an empty description becomes just the phrase", () => {
    expect(togglePhrase("", "Keep replies short.")).toBe("Keep replies short.");
  });

  test("the description never grows past the limit the server accepts", () => {
    expect(togglePhrase("x".repeat(MAX_DESCRIPTION_CHARS), "Keep replies short.").length).toBe(
      MAX_DESCRIPTION_CHARS,
    );
  });
});
