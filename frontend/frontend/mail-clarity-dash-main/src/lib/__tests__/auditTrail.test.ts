import { describe, expect, test } from "vitest";

import { AuditVerification, type AuditTrailEvent } from "../../types/audit";
import { actionLabel, fieldEntries, matchesQuery } from "../auditTrail";
import { createI18n } from "../i18n";
import { Language } from "../preferences";

const { t } = createI18n(Language.English);

const event: AuditTrailEvent = {
  id: "row-1",
  createdAt: "2026-10-08T09:00:00Z",
  action: "generate_draft",
  fields: { gmail_message_id: "18f", tone: "casual" },
  success: true,
  prevHash: null,
  currentHash: "abc123",
  verification: AuditVerification.Verified,
};

describe("audit trail helpers", () => {
  test("fields are shown key by key, exactly as recorded, with nothing invented", () => {
    expect(fieldEntries(event.fields)).toEqual([
      ["gmail_message_id", "18f"],
      ["tone", "casual"],
    ]);
    expect(fieldEntries({ text: "Masked 2 names" })).toEqual([["text", "Masked 2 names"]]);
    expect(fieldEntries({})).toEqual([]);
  });

  test("a known action is named; an unknown one is shown as its code", () => {
    expect(actionLabel("generate_draft", t)).toBe(t("audit.actions.generate_draft"));
    expect(actionLabel("brand_new_action", t)).toBe("brand_new_action");
  });

  test("the filter finds a record by action, field value or hash", () => {
    expect(matchesQuery(event, "GENERATE")).toBe(true);
    expect(matchesQuery(event, "casual")).toBe(true);
    expect(matchesQuery(event, "abc1")).toBe(true);
    expect(matchesQuery(event, "nothing like it")).toBe(false);
    expect(matchesQuery(event, "  ")).toBe(true);
  });
});
