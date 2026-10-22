// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { leaveDemo, startDemo } from "../../demo/mode";
import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { renderWithProviders } from "../../test/render";
import NotInDemo from "../NotInDemo";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, to }: { children: ReactNode; to: string }) => <a href={to}>{children}</a>,
}));

const { t } = createI18n(Language.English);
const CONSOLE = "the admin console";

afterEach(() => leaveDemo());

test("in the demo a page the demo lacks (/admin) is the normal page not found, never an error", async () => {
  const fetchSpy = vi.fn();
  vi.stubGlobal("fetch", fetchSpy);
  startDemo();
  renderWithProviders(<NotInDemo>{CONSOLE}</NotInDemo>);
  expect(await screen.findByText(t("page.notFoundTitle"))).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.queryByText(CONSOLE)).toBeNull();
  expect(fetchSpy).not.toHaveBeenCalled();
});

test("outside the demo the page itself shows", () => {
  renderWithProviders(<NotInDemo>{CONSOLE}</NotInDemo>);
  expect(screen.getByText(CONSOLE)).toBeTruthy();
});
