// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import SideNav from "../SideNav";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, to }: { children: ReactNode; to: string }) => <a href={to}>{children}</a>,
}));

const { t } = createI18n(Language.English);

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
