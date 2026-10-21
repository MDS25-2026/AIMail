import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "vitest";

import { hasLiveInbox } from "../liveInbox";

const ROUTES = join(__dirname, "..", "..", "routes");

// The stream used to open wherever AppShell was mounted; a new page in AppShell must join the list.
function pathOf(file: string): string {
  const name = file.replace(/\.tsx$/, "");
  return name === "index" ? "/" : `/${name}`;
}

test("the stream is wanted on exactly the pages that render AppShell", () => {
  const files = readdirSync(ROUTES).filter(
    (file) => file.endsWith(".tsx") && !file.startsWith("_"),
  );
  const inShell = files.filter((file) =>
    readFileSync(join(ROUTES, file), "utf8").includes("<AppShell>"),
  );
  expect(inShell.length).toBeGreaterThan(0);
  for (const file of files) expect(hasLiveInbox(pathOf(file))).toBe(inShell.includes(file));
});

test("sign-in, status and the extension preview open no stream", () => {
  expect(hasLiveInbox("/signin")).toBe(false);
  expect(hasLiveInbox("/status")).toBe(false);
  expect(hasLiveInbox("/extension")).toBe(false);
});
