import { describe, expect, test } from "vitest";

import {
  acceptRecipients,
  isLikelyAddress,
  MAX_ADDRESS_CHARS,
  MAX_RECIPIENTS,
  parseRecipients,
  splitRecipients,
} from "../recipients";

describe("recipient chips", () => {
  test("a comma, a semicolon or a new line separates recipients", () => {
    expect(parseRecipients("a@x.com, b@y.com; c@z.com\nd@w.com")).toEqual([
      "a@x.com",
      "b@y.com",
      "c@z.com",
      "d@w.com",
    ]);
  });

  test("a comma inside a quoted display name or angle brackets is part of the recipient", () => {
    expect(parseRecipients('"Lim, Daniel" <daniel@x.com>, Aina <aina@y.com>')).toEqual([
      '"Lim, Daniel" <daniel@x.com>',
      "Aina <aina@y.com>",
    ]);
    expect(parseRecipients("Ops <ops,team@x.com>; b@y.com")).toEqual([
      "Ops <ops,team@x.com>",
      "b@y.com",
    ]);
  });

  test("text after the last separator is left to finish typing", () => {
    expect(splitRecipients("a@x.com, b@")).toEqual({ complete: ["a@x.com"], rest: "b@" });
    expect(splitRecipients('"Lim, Dan')).toEqual({ complete: [], rest: '"Lim, Dan' });
  });

  test("empty pieces and stray spaces make no chips", () => {
    expect(parseRecipients(" , ;; a@x.com ,  ")).toEqual(["a@x.com"]);
    expect(parseRecipients("")).toEqual([]);
  });

  test("bare addresses and named ones look like addresses; anything else is marked", () => {
    expect(isLikelyAddress("aina@seribayu.example")).toBe(true);
    expect(isLikelyAddress("Harith Zulkifli <harith@x.com.my>")).toBe(true);
    expect(isLikelyAddress('"Lim, Daniel" <daniel@x.com>')).toBe(true);
    expect(isLikelyAddress("aina")).toBe(false);
    expect(isLikelyAddress("aina@")).toBe(false);
    expect(isLikelyAddress("Aina <aina at x.com>")).toBe(false);
    expect(isLikelyAddress("a b@x.com")).toBe(false);
  });
});

describe("recipient chips, finished text", () => {
  test("a quote or bracket left open does not swallow the separators after it", () => {
    expect(parseRecipients('"Lim, Daniel <daniel@x.com>, aina@y.com')).toEqual([
      '"Lim',
      "Daniel <daniel@x.com>",
      "aina@y.com",
    ]);
    expect(parseRecipients("Ops <ops@x.com, b@y.com")).toEqual(["Ops <ops@x.com", "b@y.com"]);
  });

  test("tabs and new lines separate a pasted column; spaces stay inside a display name", () => {
    expect(parseRecipients("Aina Rahman <a@x.com>\tb@y.com\r\nc@z.com")).toEqual([
      "Aina Rahman <a@x.com>",
      "b@y.com",
      "c@z.com",
    ]);
  });
});

describe("recipient limits", () => {
  test("no more than the limit across To and Cc are taken; the rest are handed back", () => {
    const incoming = ["a@x.com", "b@x.com", "c@x.com"];
    expect(acceptRecipients(MAX_RECIPIENTS - 2, incoming)).toEqual({
      accepted: ["a@x.com", "b@x.com"],
      tooLong: [],
      overLimit: ["c@x.com"],
    });
    expect(acceptRecipients(MAX_RECIPIENTS, incoming).accepted).toEqual([]);
  });

  test("an address longer than one may be is refused on its own", () => {
    const long = `${"a".repeat(MAX_ADDRESS_CHARS)}@x.com`;
    expect(acceptRecipients(0, [long, "b@x.com"])).toEqual({
      accepted: ["b@x.com"],
      tooLong: [long],
      overLimit: [],
    });
  });
});
