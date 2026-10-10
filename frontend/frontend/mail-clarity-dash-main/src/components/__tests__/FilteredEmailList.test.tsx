// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

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
