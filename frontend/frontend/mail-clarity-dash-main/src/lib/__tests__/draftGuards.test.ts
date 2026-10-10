import { describe, expect, test } from "vitest";

import { findRedactionMarkers, findUnfilledBlanks, hasUnsavedEdits } from "../draftGuards";

describe("findRedactionMarkers", () => {
  test("finds every marker shape the pipeline writes, in order", () => {
    const draft = "Hi [Redacted], call [PHONE_REDACTED] or see [REDACTED]. Mail [EMAIL_REDACTED].";
    expect(findRedactionMarkers(draft)).toEqual([
      "[Redacted]",
      "[PHONE_REDACTED]",
      "[REDACTED]",
      "[EMAIL_REDACTED]",
    ]);
  });

  test("returns nothing for a clean draft or ordinary brackets", () => {
    expect(findRedactionMarkers("Thanks Aisyah, see you [Thursday].")).toEqual([]);
    expect(findRedactionMarkers("")).toEqual([]);
  });
});

describe("hasUnsavedEdits", () => {
  test("is false when the reader has not typed", () => {
    expect(hasUnsavedEdits(null, "Server draft")).toBe(false);
  });

  test("is false when the typed text matches the server draft", () => {
    expect(hasUnsavedEdits("Server draft", "Server draft")).toBe(false);
  });

  test("is true when the typed text differs, including clearing it", () => {
    expect(hasUnsavedEdits("My version", "Server draft")).toBe(true);
    expect(hasUnsavedEdits("", "Server draft")).toBe(true);
  });
});

describe("saved template blanks", () => {
  test("every {{blank}} left in a draft is found, and none in a filled one", () => {
    expect(findUnfilledBlanks("Hi {{name}}, see {{ meeting link }}")).toEqual([
      "{{name}}",
      "{{ meeting link }}",
    ]);
    expect(findUnfilledBlanks("Hi Aisyah, see https://meet.example")).toEqual([]);
  });
});
