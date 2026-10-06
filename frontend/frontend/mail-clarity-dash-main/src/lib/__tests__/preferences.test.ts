import { describe, expect, test } from "vitest";

import {
  COOKIE,
  coloursAttribute,
  DEFAULT_PREFERENCES,
  parsePreferences,
  StatusColours,
} from "../preferences";

const reader = (cookies: Record<string, string>) => (name: string) => cookies[name];

describe("preference cookies", () => {
  test("no cookies means the defaults", () => {
    expect(parsePreferences(reader({}))).toEqual(DEFAULT_PREFERENCES);
  });

  test("valid values are honoured", () => {
    const parsed = parsePreferences(
      reader({
        [COOKIE.theme]: "dark",
        [COOKIE.language]: "zh",
        [COOKIE.units]: "imperial",
        [COOKIE.colours]: "friendly",
      }),
    );
    expect(parsed).toEqual({
      theme: "dark",
      language: "zh",
      units: "imperial",
      colours: "friendly",
    });
  });

  test("a hostile or unknown value falls back rather than reaching <html>", () => {
    const parsed = parsePreferences(
      reader({
        [COOKIE.theme]: '"><script>',
        [COOKIE.language]: "fr",
        [COOKIE.units]: "",
        [COOKIE.colours]: "rainbow",
      }),
    );
    expect(parsed).toEqual(DEFAULT_PREFERENCES);
  });
});

describe("colour set", () => {
  test("only the friendly set puts an attribute on the page; standard needs none", () => {
    expect(coloursAttribute(StatusColours.Friendly)).toBe("friendly");
    expect(coloursAttribute(StatusColours.Standard)).toBeUndefined();
  });
});
