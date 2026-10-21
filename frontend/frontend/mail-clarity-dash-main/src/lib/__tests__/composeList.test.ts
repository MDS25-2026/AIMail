import { describe, expect, test } from "vitest";

import { ComposeState, type ComposeDraft } from "../../types/compose";
import { EMPTY_COMPOSE_LIST, summaryOf, withDraft, withoutDraft } from "../composeList";

function draft(overrides: Partial<ComposeDraft>): ComposeDraft {
  return {
    id: "d1",
    to: [],
    cc: [],
    subject: "",
    brief: "",
    body: "",
    tone: "professional",
    state: ComposeState.Draft,
    updatedAt: "2026-10-21T09:00:00Z",
    ...overrides,
  };
}

describe("the Compose list kept in step with each save", () => {
  test("a row previews the body, or the brief before there is one, on one line", () => {
    expect(summaryOf(draft({ brief: "Tell  them\nabout leave" })).preview).toBe(
      "Tell them about leave",
    );
    expect(summaryOf(draft({ brief: "brief", body: "Hi team,\n\nBody" })).preview).toBe(
      "Hi team, Body",
    );
  });

  test("drafts are newest first, and a sent draft moves to Sent", () => {
    const older = draft({ id: "a", updatedAt: "2026-10-21T08:00:00Z" });
    const newer = draft({ id: "b", updatedAt: "2026-10-21T10:00:00Z" });
    const list = withDraft(withDraft(EMPTY_COMPOSE_LIST, older), newer);
    expect(list.drafts.map((row) => row.id)).toEqual(["b", "a"]);

    const sent = { ...older, state: ComposeState.Sent, sentAt: "2026-10-21T11:00:00Z" };
    const after = withDraft(list, sent);
    expect(after.drafts.map((row) => row.id)).toEqual(["b"]);
    expect(after.sent.map((row) => row.id)).toEqual(["a"]);
  });

  test("a deleted draft leaves both sections", () => {
    const list = withDraft(EMPTY_COMPOSE_LIST, draft({ id: "a" }));
    expect(withoutDraft(list, "a")).toEqual(EMPTY_COMPOSE_LIST);
  });
});
