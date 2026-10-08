import { describe, expect, test } from "vitest";

import { checkTone } from "../toneCheck";

describe("checkTone", () => {
  test("returns no issues for professional, clean drafts", () => {
    const draft =
      "Dear Alice,\n\nThank you for the update. We will review the documents and follow up by Friday.\n\nBest regards,\nJiaJun";
    const result = checkTone(draft);
    expect(result.hasIssues).toBe(false);
    expect(result.issueCodes).toEqual([]);
  });

  test("allows legitimate international and Malaysian enterprise acronyms", () => {
    const draft =
      "Please submit the LHDN tax form, KWSP contribution and SOCSO report before the KPI review. PDPA compliance is OK. FYI, the CEO approved the SOW.";
    const result = checkTone(draft);
    expect(result.hasIssues).toBe(false);
    expect(result.issueCodes).toEqual([]);
  });

  test("allows legitimate business dispute words like unacceptable or terrible in context", () => {
    const draft =
      "The delay on this delivery is unacceptable and the service level has been terrible. Please provide an explanation.";
    const result = checkTone(draft);
    expect(result.issueCodes).not.toContain("RUDE");
  });

  test("flags shouty all-caps words", () => {
    const draft = "You MUST DO THIS IMMEDIATELY OR ELSE";
    const result = checkTone(draft);
    expect(result.hasIssues).toBe(true);
    expect(result.issueCodes).toContain("CAPS");
  });

  test("flags excessive punctuation like !!! or ???", () => {
    const draft = "Why did you do that??? Answer me now!!!";
    const result = checkTone(draft);
    expect(result.hasIssues).toBe(true);
    expect(result.issueCodes).toContain("PUNCTUATION");
  });

  test("flags hostile or abusive vocabulary in English, Malay and Chinese", () => {
    expect(checkTone("You are an idiot and completely incompetent.").issueCodes).toContain("RUDE");
    expect(checkTone("Awak ni bodoh betul dan menyusahkan orang.").issueCodes).toContain("RUDE");
    expect(checkTone("你真是个白痴，滚吧。").issueCodes).toContain("RUDE");
  });

  test("flags excessive emoji usage (3 or more)", () => {
    const draft = "Hey there! 😊🎉🚀 Let's talk soon!";
    const result = checkTone(draft);
    expect(result.hasIssues).toBe(true);
    expect(result.issueCodes).toContain("EMOJI");
  });
});
