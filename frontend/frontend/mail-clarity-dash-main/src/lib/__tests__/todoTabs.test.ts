import { describe, expect, test } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import type { Todo } from "../../types/todo";
import { createI18n } from "../i18n";
import { Language } from "../preferences";
import { chosenTab, nextStep, parseTab, TodoTab } from "../todoTabs";

const { t } = createI18n(Language.English);
const empty = { emails: [], total: 0 };
const todo = (overrides: Partial<Todo> = {}): Todo => ({
  needsAction: empty,
  needsReview: empty,
  unsentDrafts: empty,
  waiting: [],
  waitingDays: 3,
  count: 0,
  doneToday: 0,
  ...overrides,
});

describe("the next step on a row", () => {
  test("an action item is shown as written, with how many more there are", () => {
    const email = emailFixture({ actionItems: ["Confirm the date", "Send the PO"] });
    expect(nextStep(TodoTab.Reply, email, t)).toBe(
      `Confirm the date ${t("todo.next.more", { count: 1 })}`,
    );
  });

  test("with no action item it falls back to the summary, then the subject, never an empty verb", () => {
    expect(nextStep(TodoTab.Reply, emailFixture({ aiSummary: "Asks for a quote." }), t)).toBe(
      "Reply: Asks for a quote.",
    );
    expect(nextStep(TodoTab.Reply, emailFixture({ aiSummary: "", subject: "Quote" }), t)).toBe(
      "Reply: Quote",
    );
  });
});

describe("which tab opens", () => {
  test("the one in the address, else the first with anything in it", () => {
    const withDrafts = todo({ unsentDrafts: { emails: [emailFixture()], total: 1 } });
    expect(chosenTab(withDrafts, undefined)).toBe(TodoTab.Drafts);
    expect(chosenTab(withDrafts, TodoTab.Waiting)).toBe(TodoTab.Waiting);
    expect(chosenTab(todo(), undefined)).toBe(TodoTab.Reply);
  });

  test("an unknown tab in the address is ignored", () => {
    expect(parseTab("drafts")).toBe(TodoTab.Drafts);
    expect(parseTab("spam")).toBeUndefined();
    expect(parseTab(3)).toBeUndefined();
  });
});
