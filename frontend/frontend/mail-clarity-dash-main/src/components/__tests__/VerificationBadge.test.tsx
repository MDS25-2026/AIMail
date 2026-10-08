// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { renderWithProviders } from "../../test/render";
import { AuditVerification } from "../../types/audit";
import VerificationBadge from "../audit/VerificationBadge";

const { t } = createI18n(Language.English);

function badgeFor(verification: AuditVerification): HTMLElement {
  renderWithProviders(<VerificationBadge verification={verification} />);
  return screen.getByText(t(`audit.verification.${verification}`));
}

describe("VerificationBadge", () => {
  test("a verified record reads as verified, in the success colours", () => {
    expect(badgeFor(AuditVerification.Verified).className).toContain("text-success");
  });

  test("a tampered record reads as tampered, in the danger colours", () => {
    expect(badgeFor(AuditVerification.Tampered).className).toContain("text-danger");
  });

  test("a record nobody could check is not drawn as OK", () => {
    const badge = badgeFor(AuditVerification.Unverifiable);
    expect(badge.textContent).toBe(t("audit.verification.unverifiable"));
    expect(badge.className).not.toContain("text-success");
    expect(badge.className).not.toContain("text-danger");
  });

  test("each state has its own words", () => {
    const labels = Object.values(AuditVerification).map((state) =>
      t(`audit.verification.${state}`),
    );
    expect(new Set(labels).size).toBe(labels.length);
  });
});
