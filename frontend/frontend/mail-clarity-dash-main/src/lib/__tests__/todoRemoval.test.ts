import { describe, expect, test } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import type { Todo, WaitingReply } from "../../types/todo";
import { handled, withoutEmail, withoutWaiting } from "../queries/todo";

const waitingReply = (id: string): WaitingReply => ({
  id,
  subject: "Quote",
  sentAt: "2026-10-01T00:00:00Z",
  threadId: "t1",
  workingDays: 5,
  canFollowUp: true,
  email: null,
});

const todo = (): Todo => ({
  needsAction: { emails: [emailFixture({ id: "a" }), emailFixture({ id: "b" })], total: 7 },
  needsReview: { emails: [], total: 0 },
  unsentDrafts: { emails: [], total: 0 },
  waiting: [waitingReply("w1")],
  waitingDays: 3,
  count: 8,
  doneToday: 2,
});

describe("removing a row at once", () => {
  test("a dismissed email lowers its section and the count the nav badge shows", () => {
    const after = withoutEmail(todo(), "a");
    expect(after.needsAction.total).toBe(6);
    expect(after.count).toBe(7);
  });

  test("an email not on the list changes nothing", () => {
    expect(withoutEmail(todo(), "missing").count).toBe(8);
  });

  test("not waiting removes the reply and lowers the count", () => {
    const after = withoutWaiting(todo(), "w1");
    expect(after.waiting).toEqual([]);
    expect(after.count).toBe(7);
  });

  test("a handled row counts towards done today at once", () => {
    expect(handled(todo(), withoutEmail(todo(), "a")).doneToday).toBe(3);
  });

  test("nothing removed, nothing counted as done", () => {
    expect(handled(todo(), withoutEmail(todo(), "missing")).doneToday).toBe(2);
  });
});
