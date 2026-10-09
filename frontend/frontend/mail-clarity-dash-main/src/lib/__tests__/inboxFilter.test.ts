import { describe, expect, test } from "vitest";

import { groupByThread } from "../conversations";
import { filterByPriority, PRIORITIES } from "../inboxFilter";
import type { Email, Priority } from "../../types/email";
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
