// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { emailFixture } from "../../test/emailFixture";
import { renderWithProviders } from "../../test/render";
import type { EgressRecord } from "../../types/email";
import PrivacyReceipt from "../PrivacyReceipt";

const { t } = createI18n(Language.English);

async function openReceipt(egress: EgressRecord[]) {
  renderWithProviders(<PrivacyReceipt email={emailFixture({ egress })} />);
  await userEvent.click(screen.getByText(t("receipt.open")));
}

describe("PrivacyReceipt", () => {
  test("shows each recorded request: what it was for, where it went and how much was hidden", async () => {
    await openReceipt([
      {
        purpose: "draft",
        provider: "gemini",
        chars: 812,
        hidden: { person: 2, phone: 1 },
        caught: 0,
        at: "2026-10-08T09:00:00Z",
      },
    ]);
    expect(
      screen.getByText(/Draft to Google Gemini: 812 characters, 3 details hidden/),
    ).toBeTruthy();
  });

  test("a detail the last check had to mask is called out", async () => {
    await openReceipt([
      {
        purpose: "refine",
        provider: "local",
        chars: 90,
        hidden: {},
        caught: 1,
        at: "2026-10-08T09:00:00Z",
      },
    ]);
    expect(screen.getByText(/your company's own model/)).toBeTruthy();
    expect(screen.getByText(/1 detail masked at the last check/)).toBeTruthy();
  });

  test("says plainly when nothing has gone to an AI yet", async () => {
    await openReceipt([]);
    expect(screen.getByText(t("receipt.egressNone"))).toBeTruthy();
  });
});
