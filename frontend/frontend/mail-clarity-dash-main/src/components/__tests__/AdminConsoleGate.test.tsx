// @vitest-environment jsdom
import { fireEvent, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { leaveDemo, startDemo } from "../../demo/mode";
import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import AdminConsoleGate from "../admin/AdminConsoleGate";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, to }: { children: ReactNode; to: string }) => <a href={to}>{children}</a>,
}));

const { t } = createI18n(Language.English);
const UNAUTHORIZED = 401;

afterEach(() => leaveDemo());

test("an admin signed in to the dashboard gets the console without its own sign-in", async () => {
  stubFetch({ "GET /admin/session": { body: { email: "boss@company.example" } } });
  renderWithProviders(<AdminConsoleGate />);
  expect(await screen.findByText(t("admin.title"))).toBeTruthy();
  expect(screen.queryByText(t("admin.signInTitle"))).toBeNull();
  // Nothing of the console's own to end: the dashboard's Sign out is the one that counts.
  expect(screen.queryByRole("button", { name: t("admin.signOut") })).toBeNull();
  // The console's own activity log is gone: one audit view, the Audit Trail page.
  expect(screen.getByText(t("admin.openAudit")).closest("a")?.getAttribute("href")).toBe("/audit");
});

test("when the console still refuses the session, its sign-in form is the fallback", async () => {
  stubFetch({
    "GET /admin/session": {
      status: UNAUTHORIZED,
      body: { error: { code: "admin_signed_out", message: "no admin session" } },
    },
  });
  renderWithProviders(<AdminConsoleGate />);
  expect(await screen.findByText(t("admin.signInTitle"))).toBeTruthy();
  expect(screen.queryByText(t("admin.title"))).toBeNull();
});

test("in the demo the console never calls the real admin API, whatever cookie the browser holds", async () => {
  stubFetch({ "GET /admin/session": { body: { email: "boss@company.example" } } });
  startDemo();
  renderWithProviders(<AdminConsoleGate />);
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(vi.mocked(fetch)).not.toHaveBeenCalled();
  expect(screen.queryByText(t("admin.title"))).toBeNull();
});

test("after the console's own sign-in form, its Sign out button is there", async () => {
  stubFetch({
    "GET /admin/session": {
      status: UNAUTHORIZED,
      body: { error: { code: "admin_signed_out", message: "no admin session" } },
    },
    "POST /admin/session": { body: { email: "boss@company.example" } },
  });
  renderWithProviders(<AdminConsoleGate />);
  fireEvent.change(await screen.findByLabelText(t("admin.email")), {
    target: { value: "boss@company.example" },
  });
  fireEvent.change(screen.getByLabelText(t("admin.password")), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: t("admin.signIn") }));
  expect(await screen.findByRole("button", { name: t("admin.signOut") })).toBeTruthy();
});
