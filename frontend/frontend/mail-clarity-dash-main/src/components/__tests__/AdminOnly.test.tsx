// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import AdminOnly from "../AdminOnly";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, to }: { children: ReactNode; to: string }) => <a href={to}>{children}</a>,
}));

const { t } = createI18n(Language.English);
const SESSION = { email: "a@b.c", hasMailbox: true, needsReconnect: false };
const SECRET_PAGE = "the admin page";

test("someone who is not an admin gets the app's normal page not found", async () => {
  stubFetch({ "GET /auth/session": { body: { ...SESSION, isAdmin: false } } });
  renderWithProviders(<AdminOnly>{SECRET_PAGE}</AdminOnly>);
  expect(await screen.findByText(t("page.notFoundTitle"))).toBeTruthy();
  expect(screen.getByText(t("page.notFoundBody"))).toBeTruthy();
  expect(screen.queryByText(SECRET_PAGE)).toBeNull();
});

test("an admin sees the page itself", async () => {
  stubFetch({ "GET /auth/session": { body: { ...SESSION, isAdmin: true } } });
  renderWithProviders(<AdminOnly>{SECRET_PAGE}</AdminOnly>);
  expect(await screen.findByText(SECRET_PAGE)).toBeTruthy();
  expect(screen.queryByText(t("page.notFoundTitle"))).toBeNull();
});

test("while the session is loading, neither the page nor a not-found shows", () => {
  stubFetch({ "GET /auth/session": () => new Promise(() => undefined) });
  const { container } = renderWithProviders(<AdminOnly>{SECRET_PAGE}</AdminOnly>);
  expect(container.textContent).toBe("");
});

test("a session that fails on the server shows the error state, not a missing page", async () => {
  stubFetch({ "GET /auth/session": { status: 503, body: { error: { code: "unknown" } } } });
  renderWithProviders(<AdminOnly>{SECRET_PAGE}</AdminOnly>);
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByText(t("page.errorTitle", { label: t("page.thisPage") }))).toBeTruthy();
  expect(screen.queryByText(t("page.notFoundTitle"))).toBeNull();
  expect(screen.queryByText(SECRET_PAGE)).toBeNull();
});

test("someone signed out gets the page not found", async () => {
  stubFetch({ "GET /auth/session": { status: 401, body: { error: { code: "signed_out" } } } });
  renderWithProviders(<AdminOnly>{SECRET_PAGE}</AdminOnly>);
  expect(await screen.findByText(t("page.notFoundTitle"))).toBeTruthy();
});
