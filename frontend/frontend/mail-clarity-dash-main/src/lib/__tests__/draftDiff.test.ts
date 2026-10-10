import { describe, expect, test } from "vitest";

import { diffDraft, isUnchanged } from "../draftDiff";

describe("diffDraft", () => {
  test("identical drafts have nothing marked", () => {
    const segments = diffDraft("Thanks, I will reply soon.", "Thanks, I will reply soon.");
    expect(isUnchanged(segments)).toBe(true);
  });

  test("a replaced word shows as removed then added, the rest unchanged", () => {
    const segments = diffDraft("I will reply soon.", "I will reply tomorrow.");
    expect(segments.filter((s) => s.kind === "removed").map((s) => s.text)).toEqual(["soon"]);
    expect(segments.filter((s) => s.kind === "added").map((s) => s.text)).toEqual(["tomorrow"]);
    expect(isUnchanged(segments)).toBe(false);
  });

  test("joining the segments of each side gives back that side's text", () => {
    const before = "Dear Aisyah,\n\nThe invoice is attached.";
    const after = "Dear Aisyah,\n\nThe signed invoice is attached. Thanks!";
    const segments = diffDraft(before, after);
    const side = (skip: string) =>
      segments
        .filter((s) => s.kind !== skip)
        .map((s) => s.text)
        .join("");
    expect(side("added")).toBe(before);
    expect(side("removed")).toBe(after);
  });

  test("an empty draft becomes all added", () => {
    expect(diffDraft("", "New text")).toEqual([{ text: "New text", kind: "added" }]);
  });
});
