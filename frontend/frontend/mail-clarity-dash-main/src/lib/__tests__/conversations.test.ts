import { describe, expect, test } from "vitest";

import { groupByThread, splitAround } from "../conversations";
import type { Email, ThreadMessage } from "../../types/email";
import { emailFixture } from "../../test/emailFixture";

function email(id: string, threadId: string | null, isRead: boolean): Email {
  return emailFixture({ id, threadId, isRead, timestamp: "2026-10-05T00:00:00Z" });
}

function message(timestamp: string | null, isOwnReply = false): ThreadMessage {
  return { sender: "a", snippet: "s", body: "b", isOwnReply, timestamp };
}

describe("one inbox row per conversation", () => {
  test("emails in one thread become one row, represented by the newest", () => {
    const rows = groupByThread([
      email("new", "t1", true),
      email("other", "t2", true),
      email("old", "t1", true),
    ]);
    expect(rows.map((row) => [row.email.id, row.count])).toEqual([
      ["new", 2],
      ["other", 1],
    ]);
  });

  test("a conversation is unread if any of its messages is", () => {
    const [row] = groupByThread([email("new", "t1", true), email("old", "t1", false)]);
    expect(row.isRead).toBe(false);
  });

  test("an email with no thread stands alone", () => {
    expect(groupByThread([email("a", null, true), email("b", null, true)])).toHaveLength(2);
  });
});

describe("the conversation around the open email", () => {
  test("earlier messages and the owner's replies go above, anything newer below", () => {
    const { earlier, later } = splitAround(
      [
        message("2026-10-05T01:00:00Z"),
        message("2026-10-05T02:00:00Z", true),
        message("2026-10-05T09:00:00Z"),
      ],
      "2026-10-05T03:00:00Z",
    );
    expect(earlier).toHaveLength(2);
    expect(later.map((m) => m.timestamp)).toEqual(["2026-10-05T09:00:00Z"]);
  });
});
