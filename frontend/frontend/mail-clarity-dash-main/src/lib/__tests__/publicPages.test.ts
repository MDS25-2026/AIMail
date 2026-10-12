import { expect, test } from "vitest";

import { isPublicPage } from "../publicPages";

test("the status and sign-in pages never send a signed-out visitor away; the app's pages do", () => {
  expect(isPublicPage("/status")).toBe(true);
  expect(isPublicPage("/signin")).toBe(true);
  expect(isPublicPage("/todo")).toBe(false);
  expect(isPublicPage("/")).toBe(false);
});
