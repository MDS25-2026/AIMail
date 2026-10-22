import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, test } from "vitest";

import { ActionGroup, AuditVerification, type AuditTrailEvent } from "../../types/audit";
import { actionLabel, fieldEntries, matchesQuery } from "../auditTrail";
import { createI18n } from "../i18n";
import { Language } from "../preferences";

const { t } = createI18n(Language.English);

const event: AuditTrailEvent = {
  id: "row-1",
  createdAt: "2026-10-08T09:00:00Z",
  action: "generate_draft",
  group: ActionGroup.Drafting,
  userEmail: "aina@company.example",
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

  test("the filter finds a record by action, person, field value or hash", () => {
    expect(matchesQuery(event, "GENERATE")).toBe(true);
    expect(matchesQuery(event, "aina@")).toBe(true);
    expect(matchesQuery(event, "casual")).toBe(true);
    expect(matchesQuery(event, "abc1")).toBe(true);
    expect(matchesQuery(event, "nothing like it")).toBe(false);
    expect(matchesQuery(event, "  ")).toBe(true);
  });
});

// The backend's own list of actions, read from its source so a new one cannot ship unnamed.
const AUDIT_SOURCE = readFileSync(
  join(__dirname, "../../../../../../backend/app/audit.py"),
  "utf8",
);
const BACKEND_ACTIONS = [...AUDIT_SOURCE.matchAll(/^ {4}[A-Z_]+ = "([a-z_]+)"$/gm)].map(
  (match) => match[1],
);

// Every grouped action, the listener's included, which audit.py does not list.
const GROUP_SOURCE = readFileSync(
  join(__dirname, "../../../../../../backend/app/audit_groups.py"),
  "utf8",
);
const GROUPED_ACTIONS = [...GROUP_SOURCE.matchAll(/"([a-z_]+)"/g)]
  .map((match) => match[1])
  .filter((action) => !Object.values<string>(ActionGroup).includes(action));

test("every action the backend records has a name, in all three languages", () => {
  expect(BACKEND_ACTIONS.length).toBeGreaterThan(30);
  expect(GROUPED_ACTIONS.length).toBeGreaterThan(50);
  for (const language of [Language.English, Language.Malay, Language.Chinese]) {
    const { t } = createI18n(language);
    for (const action of [...BACKEND_ACTIONS, ...GROUPED_ACTIONS]) {
      expect(actionLabel(action, t), `${language}: ${action}`).not.toBe(action);
    }
  }
});
