// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import FilteredEmailList from "../FilteredEmailList";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children }: { children: ReactNode }) => <a href="/">{children}</a>,
}));

test("Sent lists replies by when they went out, not when the email arrived", async () => {
  const arrivedFirstAnsweredLast = emailFixture({
    id: "a",
    subject: "Answered last",
    timestamp: "2026-10-01T09:00:00Z",
    sentAt: "2026-10-09T09:00:00Z",
  });
  const arrivedLastAnsweredFirst = emailFixture({
    id: "b",
    subject: "Answered first",
    timestamp: "2026-10-05T09:00:00Z",
    sentAt: "2026-10-06T09:00:00Z",
  });
  // The inbox payload is newest-arrived first.
  stubFetch({
    "GET /emails": () => ({
      body: { emails: [arrivedLastAnsweredFirst, arrivedFirstAnsweredLast], nextCursor: null },
    }),
  });
  renderWithProviders(
    <FilteredEmailList
      heading="Sent"
      description=""
      label="Sent"
      emptyTitle=""
      emptyHint=""
      filter={(email) => Boolean(email.sentAt)}
      timestampOf={(email) => email.sentAt ?? email.timestamp}
    />,
  );
  const subjects = (await screen.findAllByText(/Answered/)).map((node) => node.textContent);
  expect(subjects).toEqual(["Answered last", "Answered first"]);
});

describe("names on Sent rows (#237)", () => {
  const sent = emailFixture({
    id: "s1",
    subject: "Quote for [PERSON_2]",
    draftReply: "Hi [PERSON_2], the quote is attached.",
    sentAt: "2026-10-09T09:00:00Z",
    details: [{ kind: "PERSON", placeholder: "[PERSON_2]", value: "Daniel Lim" }],
  });

  function renderSent() {
    stubFetch({ "GET /emails": () => ({ body: { emails: [sent], nextCursor: null } }) });
    renderWithProviders(
      <FilteredEmailList
        heading="Sent"
        description=""
        label="Sent"
        emptyTitle=""
        emptyHint=""
        filter={(email) => Boolean(email.sentAt)}
        timestampOf={(email) => email.sentAt ?? email.timestamp}
      />,
    );
  }

  afterEach(() => localStorage.removeItem("aimail-hide-details"));

  test("show the real names, as the inbox does", async () => {
    renderSent();
    const preview = await screen.findByText(/the quote is attached/);
    expect(preview.closest("p")?.textContent).toBe("Hi Daniel Lim, the quote is attached.");
    expect(screen.queryByText(/\[PERSON_2\]/)).toBeNull();
  });

  test("keep the placeholders while details are hidden", async () => {
    localStorage.setItem("aimail-hide-details", "1");
    renderSent();
    expect(await screen.findByText("Hi [PERSON_2], the quote is attached.")).toBeTruthy();
  });
});
