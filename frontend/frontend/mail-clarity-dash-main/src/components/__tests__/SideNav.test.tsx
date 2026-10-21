// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import SideNav from "../SideNav";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, to }: { children: ReactNode; to: string }) => <a href={to}>{children}</a>,
}));

const demo = vi.hoisted(() => ({ isOn: false }));
vi.mock("../../demo/mode", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../demo/mode")>()),
  useIsDemo: () => demo.isOn,
}));

const { t } = createI18n(Language.English);

afterEach(() => {
  demo.isOn = false;
});

test("the side navigation leads with Compose, above the inbox", () => {
  stubFetch({
    "GET /auth/session": { body: { email: "a@b.c", hasMailbox: false, needsReconnect: false } },
  });
  renderWithProviders(<SideNav />);
  const links = screen.getAllByRole("link");
  expect(links[0].getAttribute("href")).toBe("/compose");
  expect(links[0].textContent).toBe(t("nav.compose"));
  expect(links[1].getAttribute("href")).toBe("/");
});

const NON_ADMIN = { email: "a@b.c", hasMailbox: false, needsReconnect: false, isAdmin: false };

test("someone who is not an admin is never shown Admin or the Audit Trail", async () => {
  stubFetch({ "GET /auth/session": { body: NON_ADMIN } });
  const { client } = renderWithProviders(<SideNav />);
  // Nothing on screen changes for a non-admin, so wait for the answer itself.
  await vi.waitFor(() => expect(client.getQueryData(["session"])).toEqual(NON_ADMIN));
  const hrefs = screen.getAllByRole("link").map((link) => link.getAttribute("href"));
  expect(hrefs).not.toContain("/admin");
  expect(hrefs).not.toContain("/audit");
});

test("an admin is shown Admin and the Audit Trail once the session says so", async () => {
  stubFetch({ "GET /auth/session": { body: { ...NON_ADMIN, isAdmin: true } } });
  renderWithProviders(<SideNav />);
  expect((await screen.findByText(t("nav.admin"))).getAttribute("href")).toBe("/admin");
  expect(screen.getByText(t("nav.audit")).getAttribute("href")).toBe("/audit");
});

test("while the session is still loading, no admin item flashes in", () => {
  stubFetch({ "GET /auth/session": () => new Promise(() => undefined) });
  renderWithProviders(<SideNav />);
  expect(screen.queryByText(t("nav.admin"))).toBeNull();
  expect(screen.queryByText(t("nav.audit"))).toBeNull();
});

test("in the demo the Audit Trail shows but the Admin console never does", async () => {
  demo.isOn = true;
  stubFetch({ "GET /auth/session": { body: { ...NON_ADMIN, isAdmin: true } } });
  renderWithProviders(<SideNav />);
  expect(await screen.findByText(t("nav.audit"))).toBeTruthy();
  expect(screen.queryByText(t("nav.admin"))).toBeNull();
});
