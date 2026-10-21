// @vitest-environment jsdom
import { fireEvent, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import { ActionGroup, AuditVerification, type AuditTrail } from "../../types/audit";
import AuditTrailView from "../audit/AuditTrailView";

const { t } = createI18n(Language.English);
const AINA = { id: "u-aina", email: "aina@company.example" };

const TRAIL: AuditTrail = {
  isChainIntact: true,
  totalRecords: 2,
  verifiedRecords: 2,
  failedRecords: 1,
  headHash: "f".repeat(64),
  people: [AINA],
  events: [
    {
      id: "row-2",
      createdAt: "2026-10-21T09:00:00Z",
      action: "import_inbox",
      group: ActionGroup.Mailbox,
      userEmail: AINA.email,
      fields: { imported: 20 },
      success: false,
      prevHash: "a".repeat(64),
      currentHash: "f".repeat(64),
      verification: AuditVerification.Verified,
    },
    {
      id: "row-1",
      createdAt: "2026-10-21T08:00:00Z",
      action: "renew_watch",
      group: ActionGroup.Mailbox,
      userEmail: null,
      fields: {},
      success: true,
      prevHash: null,
      currentHash: "a".repeat(64),
      verification: AuditVerification.Verified,
    },
  ],
};

/** The query of the latest GET /audit; the stub keeps paths only, the fetch mock keeps the URL. */
function lastAuditQuery(): URLSearchParams | undefined {
  const urls = vi.mocked(fetch).mock.calls.map(([url]) => new URL(String(url)));
  return urls.filter((url) => url.pathname === "/audit").at(-1)?.searchParams;
}

test("each row names its person, its plain-words action, its group and its outcome", async () => {
  stubFetch({ "GET /audit": { body: TRAIL } });
  renderWithProviders(<AuditTrailView />);
  expect(await screen.findByText(t("audit.actions.import_inbox"))).toBeTruthy();
  expect(screen.getAllByText(AINA.email).length).toBeGreaterThan(0);
  expect(screen.getByText(t("audit.system"))).toBeTruthy();
  expect(screen.getAllByText(t("audit.groups.mailbox"), { selector: "span" })).toHaveLength(2);
  expect(screen.getByText(t("audit.status.failed"))).toBeTruthy();
});

test("the summary counts the records and failures the filters match", async () => {
  stubFetch({ "GET /audit": { body: TRAIL } });
  renderWithProviders(<AuditTrailView />);
  const summary = t("audit.summary", {
    records: t("audit.recordCount", { count: 2 }),
    failures: t("audit.failureCount", { count: 1 }),
  });
  expect(await screen.findByText(summary)).toBeTruthy();
});

test("each filter is sent to the backend as its query parameter", async () => {
  stubFetch({ "GET /audit": { body: TRAIL } });
  renderWithProviders(<AuditTrailView />);
  await screen.findByText(t("audit.actions.import_inbox"));
  expect([...(lastAuditQuery()?.keys() ?? [])]).toEqual(["limit"]);

  fireEvent.change(screen.getByLabelText(t("audit.filters.person")), {
    target: { value: AINA.id },
  });
  fireEvent.change(screen.getByLabelText(t("audit.filters.group")), {
    target: { value: ActionGroup.Mailbox },
  });
  fireEvent.change(screen.getByLabelText(t("audit.filters.window")), {
    target: { value: "week" },
  });
  fireEvent.click(screen.getByLabelText(t("audit.filters.failuresOnly")));

  await vi.waitFor(() => expect(lastAuditQuery()?.get("failures_only")).toBe("true"));
  const query = lastAuditQuery();
  expect(query?.get("person")).toBe(AINA.id);
  expect(query?.get("group")).toBe(ActionGroup.Mailbox);
  expect(query?.get("window")).toBe("week");
  expect(query?.get("limit")).toBe("50");
});

test("with nothing matching, the page says so in plain words", async () => {
  stubFetch({
    "GET /audit": { body: { ...TRAIL, events: [], totalRecords: 0, failedRecords: 0 } },
  });
  renderWithProviders(<AuditTrailView />);
  expect(await screen.findByText(t("audit.noMatches"))).toBeTruthy();
});
