import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, test } from "vitest";

// A raw colour skips check-palette.py's contrast and colour-blind checks, dark mode and the friendly set.
const SRC = join(__dirname, "..", "..");
const UTILITY =
  "(?:bg|text|border|ring|outline|fill|stroke|from|via|to|divide|placeholder|accent|caret|decoration|shadow)";
const HUE =
  "(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)";
const RAW_COLOUR = new RegExp(`\\b${UTILITY}-(?:${HUE}-\\d{2,3}|white|black)\\b`, "g");

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "__tests__" ? [] : sourceFiles(path);
    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

describe("colours", () => {
  test("no raw Tailwind palette colour is used outside palette.css", () => {
    const offenders = sourceFiles(SRC).flatMap((file) =>
      [...readFileSync(file, "utf8").matchAll(RAW_COLOUR)].map(
        (match) => `${file.replace(SRC, "src")}: ${match[0]}`,
      ),
    );
    expect(offenders).toEqual([]);
  });

  test("the check itself catches a raw colour", () => {
    expect("text-amber-600 bg-white".match(RAW_COLOUR)).toEqual(["text-amber-600", "bg-white"]);
    expect("text-warning bg-surface".match(RAW_COLOUR)).toBeNull();
  });
});
