import { describe, expect, test } from "vitest";

import { COOKIE, DEFAULT_PREFERENCES, parsePreferences } from "../preferences";

const reader = (cookies: Record<string, string>) => (name: string) => cookies[name];

describe("preference cookies", () => {
  test("no cookies means the defaults", () => {
    expect(parsePreferences(reader({}))).toEqual(DEFAULT_PREFERENCES);
  });

  test("valid values are honoured", () => {
    const parsed = parsePreferences(
      reader({ [COOKIE.theme]: "dark", [COOKIE.language]: "zh", [COOKIE.units]: "imperial" }),
    );
    expect(parsed).toEqual({ theme: "dark", language: "zh", units: "imperial" });
  });

  test("a hostile or unknown value falls back rather than reaching <html>", () => {
    const parsed = parsePreferences(
      reader({ [COOKIE.theme]: '"><script>', [COOKIE.language]: "fr", [COOKIE.units]: "" }),
    );
    expect(parsed).toEqual(DEFAULT_PREFERENCES);
  });
});
