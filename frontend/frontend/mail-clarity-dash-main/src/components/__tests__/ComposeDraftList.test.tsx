// @vitest-environment jsdom
import { screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { renderWithProviders } from "../../test/render";
import { ComposeState, type ComposeSummary } from "../../types/compose";
import ComposeDraftList from "../ComposeDraftList";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children, search }: { children: ReactNode; search: { draft: string } }) => (
    <a href={`/compose?draft=${search.draft}`}>{children}</a>
  ),
}));

const { t } = createI18n(Language.English);

function row(overrides: Partial<ComposeSummary>): ComposeSummary {
  return {
    id: "d1",
    to: [],
    subject: "",
    preview: "",
    state: ComposeState.Draft,
    updatedAt: "2026-10-21T09:00:00Z",
    details: [],
    ...overrides,
  };
}

test("drafts and sent emails are listed apart, each row opening its draft", () => {
  renderWithProviders(
    <ComposeDraftList
      selectedId="d2"
      list={{
        drafts: [
          row({
            id: "d2",
            subject: "Call [PHONE_1]",
            to: ["Aina <aina@x.com>"],
            details: [{ kind: "PHONE", placeholder: "[PHONE_1]", value: "012-345 6789" }],
          }),
          row({ id: "d1", preview: "Remind the team" }),
          row({ id: "d3", subject: "Invoice", state: ComposeState.OutcomeUnknown }),
        ],
        sent: [row({ id: "s1", subject: "Payment slip", sentAt: "2026-10-20T09:00:00Z" })],
      }}
    />,
  );
  // Placeholders are filled in from the row's own details.
  expect(screen.queryByText("Call [PHONE_1]")).toBeNull();
  expect(screen.getByText("012-345 6789")).toBeTruthy();
  const drafts = within(screen.getByRole("region", { name: t("compose.draftsTitle") }));
  expect(drafts.getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual([
    "/compose?draft=d2",
    "/compose?draft=d1",
    "/compose?draft=d3",
  ]);
  expect(drafts.getByText(t("compose.noSubject"))).toBeTruthy();
  expect(drafts.getAllByText(t("compose.noRecipients"))).toHaveLength(2);
  expect(drafts.getByText(t("compose.toList", { recipients: "Aina <aina@x.com>" }))).toBeTruthy();
  // The state is said in words, not shown by colour alone.
  expect(drafts.getByText(t("compose.state.outcomeUnknown"))).toBeTruthy();
  const sent = within(screen.getByRole("region", { name: t("compose.sentTitle") }));
  expect(sent.getByText("Payment slip")).toBeTruthy();
});

test("an empty section is not shown", () => {
  renderWithProviders(
    <ComposeDraftList selectedId={undefined} list={{ drafts: [row({})], sent: [] }} />,
  );
  expect(screen.queryByRole("region", { name: t("compose.sentTitle") })).toBeNull();
});
