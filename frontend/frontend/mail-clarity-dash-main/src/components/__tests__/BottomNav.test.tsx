// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import BottomNav from "../BottomNav";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, to }: { children: ReactNode; to: string }) => <a href={to}>{children}</a>,
}));

const { t } = createI18n(Language.English);
const emptyTodo = { needsReview: { emails: [], total: 0 }, needsAction: { emails: [], total: 0 } };

test("the phone's navigation has Inbox, To-do with its count, Sent and Settings", async () => {
  stubFetch({
    "GET /auth/session": { body: { email: "a@b.c", hasMailbox: true, needsReconnect: false } },
    "GET /todo": {
      body: {
        ...emptyTodo,
        unsentDrafts: { emails: [], total: 0 },
        waiting: [],
        waitingDays: 3,
        count: 4,
      },
    },
  });
  renderWithProviders(<BottomNav />);
  expect(await screen.findByText(t("todo.countLabel", { count: 4 }))).toBeTruthy();
  const links = screen.getAllByRole("link").map((link) => link.getAttribute("href"));
  expect(links).toEqual(["/", "/todo", "/sent", "/settings"]);
});

test("without a mailbox the navigation asks for no to-do list", async () => {
  const calls = stubFetch({
    "GET /auth/session": { body: { email: "a@b.c", hasMailbox: false, needsReconnect: false } },
  });
  renderWithProviders(<BottomNav />);
  await vi.waitFor(() => expect(calls.some((call) => call.path === "/auth/session")).toBe(true));
  expect(calls.some((call) => call.path === "/todo")).toBe(false);
});
