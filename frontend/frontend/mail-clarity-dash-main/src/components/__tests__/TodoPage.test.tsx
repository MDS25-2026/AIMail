// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { emailFixture } from "../../test/emailFixture";
import { deferred, stubFetch, writes } from "../../test/fetchStub";
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

function todoBody(overrides: Record<string, unknown> = {}) {
  return {
    needsAction: empty,
    needsReview: empty,
    unsentDrafts: empty,
    waiting: [],
    waitingDays: 3,
    count: 0,
    doneToday: 0,
    ...overrides,
  };
}

const Page = () => <TodoPage onTab={() => undefined} />;

const openMenu = async () =>
  userEvent.click(await screen.findByRole("button", { name: t("todo.moreActions") }));

test("a row says the next step with the real name, and No reply needed offers Undo", async () => {
  const acting = emailFixture({
    id: "a1",
    subject: "Invoice for [PERSON_1]",
    actionItems: ["Pay by Friday", "Send the PO"],
    details: [{ placeholder: "[PERSON_1]", value: "Aisyah Rahman", kind: "PERSON" }],
  });
  const calls = stubFetch({
    "GET /todo": { body: todoBody({ needsAction: { emails: [acting], total: 1 }, count: 1 }) },
    "POST /emails/a1/dismiss": { status: 204 },
    "DELETE /emails/a1/dismiss": { status: 204 },
  });
  renderWithProviders(<Page />);
  expect(
    await screen.findByText(`Pay by Friday ${t("todo.next.more", { count: 1 })}`),
  ).toBeTruthy();
  // The row's own details: the name, as the inbox shows it, not the placeholder.
  expect(screen.getByText("Aisyah Rahman")).toBeTruthy();
  expect(screen.queryByText(/\[PERSON_1\]/)).toBeNull();
  await openMenu();
  await userEvent.click(screen.getByRole("button", { name: t("todo.dismissShort") }));
  await userEvent.click(await screen.findByRole("button", { name: t("todo.undo") }));
  await vi.waitFor(() =>
    expect(writes(calls).map((call) => `${call.method} ${call.path}`)).toEqual([
      "POST /emails/a1/dismiss",
      "DELETE /emails/a1/dismiss",
    ]),
  );
});

test("the tabs show each list's count and open on the first with anything in it", async () => {
  const review = emailFixture({ id: "r1", reviewReasons: [] });
  stubFetch({
    "GET /todo": {
      body: todoBody({ needsReview: { emails: [review], total: 1 }, count: 1, doneToday: 3 }),
    },
  });
  renderWithProviders(<Page />);
  const selected = await screen.findByRole("tab", { selected: true });
  expect(selected.textContent).toContain(t("todo.needsReview"));
  expect(screen.getAllByRole("tab")).toHaveLength(4);
  expect(screen.getByText(`Check the draft: ${t("todo.flagged")}`)).toBeTruthy();
  expect(screen.getByText(t("todo.progress", { done: 3, left: 1 }))).toBeTruthy();
});

test("five rows show first, and the rest are one click away", async () => {
  const emails = Array.from({ length: 7 }, (_, index) =>
    emailFixture({ id: `e${index}`, actionItems: [`Task ${index}`] }),
  );
  stubFetch({ "GET /todo": { body: todoBody({ needsAction: { emails, total: 7 }, count: 7 }) } });
  renderWithProviders(<Page />);
  await screen.findByText("Task 0");
  expect(screen.queryByText("Task 6")).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: t("todo.showRest", { count: 2 }) }));
  expect(screen.getByText("Task 6")).toBeTruthy();
});

test("Remind me later snoozes the email and takes it off the list", async () => {
  const acting = emailFixture({ id: "a1", actionItems: ["Pay by Friday"] });
  const calls = stubFetch({
    // As the server does: once snoozed, the email is off the list.
    "GET /todo": () => ({
      body: calls.some((each) => each.path.endsWith("/snooze"))
        ? todoBody()
        : todoBody({ needsAction: { emails: [acting], total: 1 }, count: 1 }),
    }),
    "GET /settings/quiet-hours": { status: 404 },
    "POST /emails/a1/snooze": { body: acting },
  });
  renderWithProviders(<Page />);
  await openMenu();
  await userEvent.click(screen.getByRole("button", { name: t("todo.remindLater") }));
  await userEvent.click(screen.getByRole("button", { name: t("snooze.tomorrow") }));
  await vi.waitFor(() =>
    expect(writes(calls).map((call) => call.path)).toEqual(["/emails/a1/snooze"]),
  );
  expect(screen.queryByText("Pay by Friday")).toBeNull();
});

test("with nothing left, the page says all clear and what will appear here", async () => {
  stubFetch({ "GET /todo": { body: todoBody() } });
  renderWithProviders(<Page />);
  expect(await screen.findByText(t("todo.allClearTitle"))).toBeTruthy();
  expect(screen.queryByRole("tablist")).toBeNull();
});

test("a reply sent through AIMail gets a follow-up drafted with real names, edited and sent", async () => {
  // The row's own numbering differs from the thread's: the draft must use the thread's.
  const answered = emailFixture({
    id: "a2",
    details: [{ placeholder: "[PERSON_1]", value: "Someone Else", kind: "PERSON" }],
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
        doneToday: 0,
      },
    },
    "POST /todo/waiting/w2/follow-up": {
      body: {
        draft: "Hi [PERSON_1], just following up.",
        details: [{ placeholder: "[PERSON_1]", value: "Aisyah Rahman", kind: "PERSON" }],
      },
    },
    "POST /todo/waiting/w2/follow-up/send": { status: 204 },
  });
  renderWithProviders(<Page />);
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
        doneToday: 0,
      },
    },
  });
  renderWithProviders(<Page />);
  expect(await screen.findByRole("link", { name: t("todo.openInGmail") })).toBeTruthy();
  expect(screen.queryByRole("button", { name: t("todo.draftFollowUp") })).toBeNull();
});

test("a follow-up with text left for the reader asks once, then sends anyway", async () => {
  const waiting = {
    id: "w4",
    subject: "Re: Quote",
    sentAt: "2026-10-01T02:00:00Z",
    threadId: "18f2d",
    workingDays: 5,
    email: emailFixture({ id: "a4" }),
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
        doneToday: 0,
      },
    },
    "POST /todo/waiting/w4/follow-up": {
      body: { draft: "Following up. Regards, [Your Name]", details: [] },
    },
    "POST /todo/waiting/w4/follow-up/send": { status: 204 },
  });
  renderWithProviders(<Page />);
  await userEvent.click(await screen.findByRole("button", { name: t("todo.draftFollowUp") }));
  await userEvent.click(await screen.findByRole("button", { name: t("todo.sendFollowUp") }));
  expect(screen.getByRole("alert").textContent).toBe(t("draftStatus.sendTemplates", { count: 1 }));
  const sends = () => writes(calls).filter((call) => call.path.endsWith("/send"));
  expect(sends()).toHaveLength(0);
  await userEvent.click(screen.getByRole("button", { name: t("draftStatus.sendAnyway") }));
  await vi.waitFor(() => expect(sends()).toHaveLength(1));
});

test("dismissing takes the row out at once, and puts it back if the server refuses", async () => {
  const acting = emailFixture({ id: "a1", subject: "Invoice", actionItems: ["Pay by Friday"] });
  const answer = deferred<{ status: number }>();
  stubFetch({
    "GET /todo": {
      body: {
        needsAction: { emails: [acting], total: 1 },
        needsReview: empty,
        unsentDrafts: empty,
        waiting: [],
        waitingDays: 3,
        count: 1,
        doneToday: 0,
      },
    },
    "POST /emails/a1/dismiss": () => answer.promise,
  });
  renderWithProviders(<Page />);
  expect(await screen.findByText("Pay by Friday")).toBeTruthy();
  await openMenu();
  await userEvent.click(screen.getByRole("button", { name: t("todo.dismissShort") }));
  // Gone while the server is still thinking.
  expect(screen.queryByText("Pay by Friday")).toBeNull();
  answer.resolve({ status: 500 });
  expect(await screen.findByText("Pay by Friday")).toBeTruthy();
});
