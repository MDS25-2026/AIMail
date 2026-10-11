import { expect, test } from "vitest";

import { createI18n } from "../i18n";
import { Language } from "../preferences";
import { reviewReasonText } from "../reviewReasons";
import { ReviewCode } from "../../types/email";

const { t } = createI18n(Language.English);

test("each reason reads as a sentence, with its items", () => {
  expect(reviewReasonText({ code: ReviewCode.DoesNotAddress, items: ["the refund date"] }, t)).toBe(
    "It may not answer: the refund date.",
  );
  expect(reviewReasonText({ code: ReviewCode.LowConfidence, items: [] }, t)).toBe(
    "The AI check isn't confident in this draft.",
  );
});

test("personal-detail reasons name the kind of detail, never a code", () => {
  const text = reviewReasonText(
    { code: ReviewCode.PiiFound, items: ["MY_NRIC", "SOMETHING_NEW"] },
    t,
  );
  expect(text).toBe("The draft may contain personal details: an IC number, another detail.");
  expect(text).not.toMatch(/MY_NRIC|SOMETHING_NEW/);
});

test("a code from a newer agent reads as flagged for review, not as the code", () => {
  const text = reviewReasonText({ code: "brand_new_check" as ReviewCode, items: [] }, t);
  expect(text).toBe("Flagged for your review.");
});

test("every code has words in Malay and Chinese too", () => {
  for (const language of [Language.Malay, Language.Chinese]) {
    const local = createI18n(language).t;
    for (const code of Object.values(ReviewCode)) {
      expect(reviewReasonText({ code, items: [] }, local)).not.toMatch(/review\.reasons/);
    }
  }
});
