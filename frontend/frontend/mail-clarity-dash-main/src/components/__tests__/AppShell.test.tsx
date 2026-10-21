// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import AppShell from "../AppShell";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, to }: { children: ReactNode; to: string }) => <a href={to}>{children}</a>,
  useNavigate: () => vi.fn(),
}));
vi.mock("../../lib/useIsReadingEmail", () => ({ useIsReadingEmail: () => false }));
vi.mock("../SideNav", () => ({ default: () => null }));
vi.mock("../BottomNav", () => ({ default: () => null }));
vi.mock("../InboxChatWidget", () => ({ default: () => <p>inbox assistant</p> }));

test("the inbox assistant is part of the signed-in app, not the site's public pages", async () => {
  stubFetch({
    "GET /auth/session": { body: { email: "a@b.c", hasMailbox: true, needsReconnect: false } },
  });
  renderWithProviders(
    <AppShell>
      <p>page</p>
    </AppShell>,
  );
  expect(await screen.findByText("inbox assistant")).toBeTruthy();
});
