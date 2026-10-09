import { describe, expect, test } from "vitest";

import { groupByThread } from "../conversations";
import {
  CATEGORIES,
  CATEGORY_MIN_CONFIDENCE,
  filterByCategory,
  filterByPriority,
  PRIORITIES,
  shownCategory,
} from "../inboxFilter";
import type { Email, EmailCategory, Priority } from "../../types/email";
import { emailFixture } from "../../test/emailFixture";

function email(id: string, priority: Priority, threadId: string | null = null): Email {
  return emailFixture({ id, priority, threadId, timestamp: "2026-10-09T00:00:00Z" });
}

const ids = (emails: Email[], filter: Parameters<typeof filterByPriority>[1]) =>
  filterByPriority(groupByThread(emails), filter).map(({ email }) => email.id);

describe("the inbox priority filter", () => {
  const inbox = [
    email("c", "critical"),
    email("h", "high"),
    email("m", "medium"),
    email("l", "low"),
  ];

  test("all keeps every conversation, in order", () => {
    expect(ids(inbox, "all")).toEqual(["c", "h", "m", "l"]);
  });

  test("one priority keeps only the conversations with it", () => {
    expect(ids(inbox, "critical")).toEqual(["c"]);
    expect(ids(inbox, "low")).toEqual(["l"]);
  });

  test("a priority nothing has leaves an empty list", () => {
    expect(ids([email("h", "high")], "critical")).toEqual([]);
  });

  test("a thread is judged by its newest email, the one its row shows", () => {
    const thread = [email("newest", "low", "t1"), email("older", "critical", "t1")];
    expect(ids(thread, "low")).toEqual(["newest"]);
    expect(ids(thread, "critical")).toEqual([]);
  });

  test("offers every priority, most urgent first", () => {
    expect(PRIORITIES).toEqual(["critical", "high", "medium", "low"]);
  });
});

function classified(id: string, category: EmailCategory, confidence: number | null): Email {
  return emailFixture({ id, category, categoryConfidence: confidence });
}

describe("which category an email shows", () => {
  test("a confident classification is shown", () => {
    expect(shownCategory(classified("a", "vendor", 0.92))).toBe("vendor");
    expect(shownCategory(classified("b", "client", CATEGORY_MIN_CONFIDENCE))).toBe("client");
  });

  test("an unclassified email shows nothing, not the API's internal default", () => {
    expect(shownCategory(classified("a", "internal", null))).toBeNull();
    expect(shownCategory(emailFixture({ category: "internal" }))).toBeNull();
  });

  test("an unsure classification shows nothing", () => {
    expect(shownCategory(classified("a", "security", 0.31))).toBeNull();
  });
});

describe("the inbox category filter", () => {
  const inbox = [
    classified("v", "vendor", 0.9),
    classified("s", "security", 0.8),
    classified("u", "internal", null),
    classified("low", "vendor", 0.2),
  ];
  const ids = (filter: Parameters<typeof filterByCategory>[1]) =>
    filterByCategory(groupByThread(inbox), filter).map(({ email }) => email.id);

  test("all keeps every conversation, classified or not", () => {
    expect(ids("all")).toEqual(["v", "s", "u", "low"]);
  });

  test("a category keeps only rows confidently shown as it", () => {
    expect(ids("vendor")).toEqual(["v"]);
    expect(ids("internal")).toEqual([]);
  });

  test("offers the six categories in the taxonomy's order", () => {
    expect(CATEGORIES).toEqual(["client", "vendor", "internal", "security", "admin", "personal"]);
  });
});
