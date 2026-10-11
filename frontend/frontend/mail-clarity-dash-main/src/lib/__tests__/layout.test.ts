import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, test } from "vitest";

// #96: an absolutely positioned sr-only label inside a scroller with no positioned ancestor is
// placed against the page, escapes the clipping, and stretches the document into blank space
// (4211px on a 900px viewport, measured). Every scroll or clip container must be a containing block.
const SRC = join(__dirname, "..", "..");
const SCROLLER = /overflow-(?:y-|x-)?(?:auto|hidden|scroll)/;
// Any of these makes a containing block; "relative" beside "fixed" would undo the fixed one.
const POSITIONED = /(?:^|\s)(?:relative|absolute|fixed|sticky)(?:\s|$)/;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory())
      return entry.name === "ui" || entry.name === "__tests__" ? [] : sourceFiles(path);
    return path.endsWith(".tsx") ? [path] : [];
  });
}

describe("scroll containers", () => {
  test("every scroll or clip container is positioned, so sr-only text cannot stretch the page", () => {
    const offenders = sourceFiles(SRC).flatMap((file) =>
      [...readFileSync(file, "utf8").matchAll(/className="([^"]*)"/g)]
        .map((match) => match[1])
        .filter((classes) => SCROLLER.test(classes) && !POSITIONED.test(classes))
        .map((classes) => `${file.replace(SRC, "src")}: ${classes}`),
    );
    expect(offenders).toEqual([]);
  });
});
