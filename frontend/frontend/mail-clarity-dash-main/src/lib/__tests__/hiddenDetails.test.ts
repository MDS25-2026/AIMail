import { describe, expect, it } from "vitest";

import { fillFirst, hiddenCounts, HiddenKind, kindOf, unfilledMarkers } from "../hiddenDetails";

const KNOWN = new Map([["[PERSON_1]", "Aisyah"]]);

describe("hidden details", () => {
  it("names the kind of detail behind each marker", () => {
    expect(kindOf("[PERSON_2]")).toBe(HiddenKind.Name);
    expect(kindOf("[PHONE_1]")).toBe(HiddenKind.Phone);
    expect(kindOf("[IC_REDACTED]")).toBe(HiddenKind.Id);
    expect(kindOf("(name)")).toBe(HiddenKind.Name);
    expect(kindOf("[Redacted]")).toBe(HiddenKind.Other);
  });

  it("lists only what will not be filled in at send, in reading order", () => {
    const draft = "Hi [PERSON_1], call [PHONE_1] or ask (hidden). Thanks, [PERSON_1]";
    expect(unfilledMarkers(draft, KNOWN)).toEqual(["[PHONE_1]", "(hidden)"]);
  });

  it("fills in one marker at a time and ignores an empty value", () => {
    const draft = "Ask [Redacted] or [Redacted].";
    expect(fillFirst(draft, "[Redacted]", " Farid ")).toBe("Ask Farid or [Redacted].");
    expect(fillFirst(draft, "[Redacted]", "  ")).toBe(draft);
    expect(fillFirst(draft, "[PHONE_1]", "012")).toBe(draft);
  });

  it("counts each hidden person once however often they are named", () => {
    const body = "[PERSON_1] and [PERSON_1] met [PERSON_2]; call [PHONE_1]. [Redacted]";
    expect(hiddenCounts(body)).toEqual([
      { kind: HiddenKind.Name, count: 2 },
      { kind: HiddenKind.Phone, count: 1 },
      { kind: HiddenKind.Other, count: 1 },
    ]);
  });

  it("has nothing to count in text with no hidden details", () => {
    expect(hiddenCounts("Is Thursday still on?")).toEqual([]);
  });
});
