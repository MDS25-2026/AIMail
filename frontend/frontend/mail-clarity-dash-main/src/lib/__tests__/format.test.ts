import { describe, expect, test } from "vitest";

import { formatNumber, formatTimestamp } from "../formatTimestamp";
import { Language } from "../preferences";

describe("formatting", () => {
  test("an unparseable timestamp is shown as received rather than as 'Invalid Date'", () => {
    expect(formatTimestamp("not a date")).toBe("not a date");
  });

  test.each(Object.values(Language))("a timestamp formats in %s", (language) => {
    expect(formatTimestamp("2026-09-30T08:15:00Z", language)).toMatch(/30/);
  });

  test("an email from an earlier year shows its year; one from this year does not", () => {
    const now = new Date("2026-10-10T00:00:00Z");
    expect(formatTimestamp("2025-12-30T08:15:00Z", Language.English, now)).toMatch(/2025/);
    expect(formatTimestamp("2026-09-30T08:15:00Z", Language.English, now)).not.toMatch(/2026/);
  });

  test("numbers keep their value in every language", () => {
    for (const language of Object.values(Language)) {
      expect(formatNumber(1250.5, language).replace(/\D/g, "")).toBe("12505");
    }
  });
});
