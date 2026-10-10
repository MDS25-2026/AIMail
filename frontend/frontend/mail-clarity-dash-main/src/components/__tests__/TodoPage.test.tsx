// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { emailFixture } from "../../test/emailFixture";
import { stubFetch, writes } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import TodoPage from "../TodoPage";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, className }: { children: ReactNode; className?: string }) => (
    <a href="/" className={className}>
      {children}
    </a>
  ),
}));
vi.mock("../AppShell", () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const { t } = createI18n(Language.English);
const empty = { emails: [], total: 0 };

test("each section lists what needs the reader, and No reply needed takes an email out", async () => {
  const acting = emailFixture({
    id: "a1",
    subject: "Invoice for [PERSON_1]",
    actionItems: ["Pay by Friday"],
    details: [{ placeholder: "[PERSON_1]", value: "Aisyah Rahman", kind: "PERSON" }],
  });
  const calls = stubFetch({
    "GET /todo": {
      body: {
        needsAction: { emails: [acting], total: 1 },
        needsReview: empty,
        unsentDrafts: empty,
        waiting: [
          {
            id: "w1",
            subject: "Re: PO",
            sentAt: "2026-10-01T02:00:00Z",
            threadId: "18f2a",
            workingDays: 4,
            email: null,
            canFollowUp: false,
          },
        ],
        waitingDays: 3,
        count: 2,
      },
    },
    "POST /emails/a1/dismiss": { status: 204 },
  });
  renderWithProviders(<TodoPage />);
  expect(await screen.findByText("Pay by Friday")).toBeTruthy();
  // The row's own details: the name, as the inbox shows it, not the placeholder.
  expect(screen.getByText("Aisyah Rahman")).toBeTruthy();
  expect(screen.queryByText(/\[PERSON_1\]/)).toBeNull();
  expect(screen.getByText("Re: PO")).toBeTruthy();
  const gmail = screen.getByRole("link", { name: t("todo.openInGmail") });
  expect(gmail.getAttribute("href")).toContain("#all/18f2a");
  await userEvent.click(screen.getByRole("button", { name: t("todo.noReplyNeeded") }));
  await vi.waitFor(() =>
    expect(writes(calls).map((call) => call.path)).toEqual(["/emails/a1/dismiss"]),
  );
});

test("a reply sent through AIMail gets a follow-up drafted with real names, edited and sent", async () => {
  const answered = emailFixture({
    id: "a2",
    details: [{ placeholder: "[PERSON_1]", value: "Aisyah Rahman", kind: "PERSON" }],
  });
  const waiting = {
    id: "w2",
    subject: "Re: Invoice",
    sentAt: "2026-10-01T02:00:00Z",
    threadId: "18f2b",
    workingDays: 5,
    email: answered,
    canFollowUp: true,
  };
  const calls = stubFetch({
    "GET /todo": {
      body: {
        needsAction: empty,
        needsReview: empty,
        unsentDrafts: empty,
        waiting: [waiting],
        waitingDays: 3,
        count: 1,
      },
    },
    "POST /todo/waiting/w2/follow-up": { body: { draft: "Hi [PERSON_1], just following up." } },
    "POST /todo/waiting/w2/follow-up/send": { status: 204 },
  });
  renderWithProviders(<TodoPage />);
  await userEvent.click(await screen.findByRole("button", { name: t("todo.draftFollowUp") }));
  const editor = await screen.findByLabelText(t("todo.followUpLabel"));
  expect((editor as HTMLTextAreaElement).value).toBe("Hi Aisyah Rahman, just following up.");
  await userEvent.type(editor, " Thanks!");
  await userEvent.click(screen.getByRole("button", { name: t("todo.sendFollowUp") }));
  await vi.waitFor(() =>
    expect(writes(calls).find((call) => call.path.endsWith("/send"))?.body).toEqual({
      draft: "Hi Aisyah Rahman, just following up. Thanks!",
    }),
  );
});

test("a reply sent from Gmail is followed up in Gmail only", async () => {
  stubFetch({
    "GET /todo": {
      body: {
        needsAction: empty,
        needsReview: empty,
        unsentDrafts: empty,
        waiting: [
          {
            id: "w3",
            subject: "Re: PO",
            sentAt: "2026-10-01T02:00:00Z",
            threadId: "18f2c",
            workingDays: 4,
            email: null,
            canFollowUp: false,
          },
        ],
        waitingDays: 3,
        count: 1,
      },
    },
  });
  renderWithProviders(<TodoPage />);
  expect(await screen.findByRole("link", { name: t("todo.openInGmail") })).toBeTruthy();
  expect(screen.queryByRole("button", { name: t("todo.draftFollowUp") })).toBeNull();
});
