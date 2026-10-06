import { describe, expect, test } from "vitest";

import { detailSegments, detailValues, hasMissingDetails, restoreDetails } from "../details";
import { findTemplatePlaceholders } from "../draftGuards";

const values = detailValues([
  { placeholder: "[PERSON_1]", value: "Aisyah Rahman", kind: "PERSON" },
  { placeholder: "[PHONE_1]", value: "012-345 6789", kind: "PHONE" },
]);

describe("restorable masking in the dashboard", () => {
  test("placeholders are shown as the owner's real details", () => {
    expect(restoreDetails("Hi [PERSON_1], call [PHONE_1].", values)).toBe(
      "Hi Aisyah Rahman, call 012-345 6789.",
    );
  });

  test("a placeholder with no known value stays visible rather than guessed", () => {
    expect(restoreDetails("Hi [PERSON_2]", values)).toBe("Hi [PERSON_2]");
    expect(hasMissingDetails("Hi [PERSON_2]", values)).toBe(true);
    expect(hasMissingDetails("Hi [PERSON_1], [Redacted]", values)).toBe(false);
  });

  test("each restored detail is marked so the reader knows the AI never saw it", () => {
    expect(detailSegments("Hi [PERSON_1]!", values)).toEqual([
      { text: "Hi ", isDetail: false },
      { text: "Aisyah Rahman", isDetail: true },
      { text: "!", isDetail: false },
    ]);
  });

  test("template gaps the model invents are caught, restorable placeholders are not", () => {
    expect(findTemplatePlaceholders("Regards, [Your Name] at [Company]")).toEqual([
      "[Your Name]",
      "[Company]",
    ]);
    expect(findTemplatePlaceholders("Hi [PERSON_1], see [Redacted] and [PHONE_12]")).toEqual([]);
  });
});
