// @vitest-environment jsdom
import { act, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { deferred, stubFetch, type StubReply } from "../../test/fetchStub";
import { emailFixture } from "../../test/emailFixture";
import { renderHookWithProviders } from "../../test/render";
import type { Email } from "../../types/email";
import { ConfirmKind, useDraftWorkflow } from "../useDraftWorkflow";

const first = emailFixture({ id: "a", draftReply: "Draft for A" });
const second = emailFixture({ id: "b", draftReply: "Draft for B" });

function renderWorkflow(email: Email) {
  return renderHookWithProviders((current: Email) => useDraftWorkflow(current), {
    initialProps: email,
  });
}

describe("switching emails mid-request", () => {
  test("a late answer for the previous email leaves the new email's edits alone", async () => {
    const answer = deferred<StubReply>();
    stubFetch({ "POST /emails/a/refine": () => answer.promise });
    const { result, rerender } = renderWorkflow(first);

    let refining: Promise<void> = Promise.resolve();
    act(() => {
      refining = result.current.refine("Shorter");
    });
    rerender(second);
    act(() => result.current.setDraft("My own words for B"));
    await act(async () => {
      answer.resolve({ body: { ...first, draftReply: "Refined A" } });
      await refining;
    });

    expect(result.current.draft).toBe("My own words for B");
    expect(result.current.status.failure).toBeNull();
  });

  test("a late failure for the previous email is not shown on the new one", async () => {
    const answer = deferred<StubReply>();
    stubFetch({ "POST /emails/a/refine": () => answer.promise });
    const { result, rerender } = renderWorkflow(first);

    let refining: Promise<void> = Promise.resolve();
    act(() => {
      refining = result.current.refine("Shorter").catch(() => undefined);
    });
    rerender(second);
    await act(async () => {
      answer.resolve({ status: 502, body: { error: { code: "agent_unavailable" } } });
      await refining;
    });

    expect(result.current.status.failure).toBeNull();
    rerender(first);
    expect(result.current.status.failure).not.toBeNull();
  });
});

describe("sending a draft that still has redaction markers", () => {
  const marked = emailFixture({ id: "m", draftReply: "Dear [Redacted], thanks." });

  test("asks first and sends nothing until the reader decides", () => {
    const calls = stubFetch({});
    const { result } = renderWorkflow(marked);
    act(() => result.current.send());
    expect(result.current.status.pendingConfirm).toEqual({
      kind: ConfirmKind.SendMarkers,
      markerCount: 1,
    });
    expect(calls).toEqual([]);
  });

  test("typing over every marker withdraws the question", () => {
    stubFetch({});
    const { result } = renderWorkflow(marked);
    act(() => result.current.send());
    act(() => result.current.setDraft("Dear Aisyah, thanks."));
    expect(result.current.status.pendingConfirm).toBeNull();
  });

  test("sending anyway sends the draft as it is at that moment, after the undo window", async () => {
    vi.useFakeTimers();
    const calls = stubFetch({ "POST /emails/m/send": { body: { ...marked, sentAt: "now" } } });
    const { result } = renderWorkflow(marked);
    act(() => result.current.send());
    act(() => result.current.setDraft("Dear [Redacted], thanks again."));
    act(() => result.current.status.onConfirm());
    expect(calls).toEqual([]); // the undo window runs first
    act(() => vi.advanceTimersByTime(5_000));
    vi.useRealTimers();
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0].body).toEqual({ draft: "Dear [Redacted], thanks again." });
    expect(result.current.status.pendingConfirm).toBeNull();
  });
});

describe("waiting for the worker's first draft", () => {
  test("an email still being drafted shows as generating and cannot be sent", () => {
    stubFetch({});
    const { result } = renderWorkflow(emailFixture({ id: "c", draftReply: "", isDrafting: true }));
    expect(result.current.status.isGenerating).toBe(true);
    expect(result.current.isBusy).toBe(true);
  });

  test("once the draft arrives the panel is free again", () => {
    stubFetch({});
    const { result } = renderWorkflow(emailFixture({ id: "c", isDrafting: false }));
    expect(result.current.status.isGenerating).toBe(false);
    expect(result.current.isBusy).toBe(false);
  });
});

describe("a sent reply is final (#172)", () => {
  test("the draft is locked once sent, and a regenerate asks nothing of the backend", () => {
    const calls = stubFetch({});
    const sent = emailFixture({ id: "s", sentAt: "2026-10-08T10:00:00Z" });
    const { result } = renderWorkflow(sent);
    expect(result.current.isDraftLocked).toBe(true);
    expect(result.current.isBusy).toBe(false);
    act(() => result.current.regenerate());
    expect(calls).toEqual([]);
  });

  test("an unsent draft that nothing is changing stays editable", () => {
    stubFetch({});
    const { result } = renderWorkflow(emailFixture({ id: "u" }));
    expect(result.current.isDraftLocked).toBe(false);
  });
});

describe("the undo window", () => {
  afterEach(() => vi.useRealTimers());

  test("Send waits out the countdown, and Undo means nothing is sent", () => {
    vi.useFakeTimers();
    const calls = stubFetch({});
    const { result } = renderWorkflow(
      emailFixture({ id: "w", draftReply: "Thanks, see you Friday." }),
    );
    act(() => result.current.send());
    expect(result.current.undoCountdown).toBe(5);
    expect(result.current.isDraftLocked).toBe(true);
    act(() => result.current.undoSend());
    act(() => vi.advanceTimersByTime(6_000));
    expect(result.current.undoCountdown).toBeNull();
    expect(calls).toEqual([]);
  });
});

describe("send anyway (#145)", () => {
  afterEach(() => vi.useRealTimers());

  test("confirming a leftover-marker warning still starts the undo countdown, not an instant send", () => {
    vi.useFakeTimers();
    const calls = stubFetch({});
    const { result } = renderWorkflow(
      emailFixture({ id: "m", draftReply: "Thanks, we will call [PHONE_REDACTED] on Friday." }),
    );
    act(() => result.current.send());
    expect(result.current.status.pendingConfirm?.kind).toBe(ConfirmKind.SendMarkers);
    act(() => result.current.status.onConfirm());
    expect(result.current.undoCountdown).toBe(5);
    expect(calls).toEqual([]);
  });

  test("the checks after a confirmed warning still run: the tone warning comes next", () => {
    stubFetch({});
    const { result } = renderWorkflow(
      emailFixture({
        id: "t",
        draftReply: "Call [PHONE_REDACTED]. THIS IS UNACCEPTABLE AND STUPID!!!",
      }),
    );
    act(() => result.current.send());
    act(() => result.current.status.onConfirm());
    expect(result.current.status.pendingConfirm?.kind).toBe(ConfirmKind.ToneWarning);
    expect(result.current.undoCountdown).toBeNull();
  });
});

describe("each email keeps its own state (#138)", () => {
  test("edits made on one email are still there after opening another and coming back", () => {
    stubFetch({});
    const { result, rerender } = renderWorkflow(first);
    act(() => result.current.setDraft("My edit to A"));
    rerender(second);
    act(() => result.current.setDraft("My edit to B"));
    rerender(first);
    expect(result.current.draft).toBe("My edit to A");
    rerender(second);
    expect(result.current.draft).toBe("My edit to B");
  });

  test("a regenerate running on one email does not lock another", () => {
    const answer = deferred<StubReply>();
    stubFetch({ "POST /emails/a/regenerate": () => answer.promise });
    const { result, rerender } = renderWorkflow(first);
    act(() => result.current.regenerate());
    expect(result.current.isDraftLocked).toBe(true);
    rerender(second);
    expect(result.current.isRegenerating).toBe(false);
    expect(result.current.isDraftLocked).toBe(false);
  });
});

describe("changing the tone", () => {
  test("a failed regenerate puts the tone back to the one the draft is written in", async () => {
    stubFetch({
      "POST /emails/r/regenerate": { status: 502, body: { error: { code: "agent_unavailable" } } },
    });
    const { result } = renderWorkflow(emailFixture({ id: "r", tone: "professional" }));
    act(() => result.current.setTone("casual"));
    expect(result.current.tone).toBe("casual");
    await waitFor(() => expect(result.current.status.failure).not.toBeNull());
    expect(result.current.tone).toBe("professional");
  });

  test("a regenerate that works keeps the new tone", async () => {
    const casual = emailFixture({ id: "s", tone: "casual", draftReply: "Hey, sounds good!" });
    stubFetch({ "POST /emails/s/regenerate": { body: casual } });
    const { result } = renderWorkflow(emailFixture({ id: "s", tone: "professional" }));
    act(() => result.current.setTone("casual"));
    await waitFor(() => expect(result.current.isRegenerating).toBe(false));
    expect(result.current.tone).toBe("casual");
  });
});

describe("what the Changes view compares (#149)", () => {
  const original = emailFixture({ id: "c", draftReply: "Thanks, I will reply soon." });
  const refined = { ...original, draftReply: "Thanks, I will reply by Friday." };

  async function refineTo(result: { current: ReturnType<typeof useDraftWorkflow> }) {
    await act(async () => {
      await result.current.refine("Add a deadline");
    });
  }

  test("an untouched draft compares the AI draft with itself", () => {
    stubFetch({});
    const { result } = renderWorkflow(original);
    expect(result.current.comparison).toEqual({
      before: "Thanks, I will reply soon.",
      after: "Thanks, I will reply soon.",
      source: "edits",
    });
  });

  test("typed edits compare the AI draft with the reader's text", () => {
    stubFetch({});
    const { result } = renderWorkflow(original);
    act(() => result.current.setDraft("Thanks, I will reply tomorrow."));
    expect(result.current.comparison).toEqual({
      before: "Thanks, I will reply soon.",
      after: "Thanks, I will reply tomorrow.",
      source: "edits",
    });
  });

  test("after a Refine, it compares the text Refine was given with the refined draft", async () => {
    stubFetch({ "POST /emails/c/refine": { body: refined } });
    const { result, rerender } = renderWorkflow(original);
    act(() => result.current.setDraft("Thanks, I will reply later."));
    await refineTo(result);
    rerender(refined);
    expect(result.current.comparison).toEqual({
      before: "Thanks, I will reply later.",
      after: "Thanks, I will reply by Friday.",
      source: "refine",
    });
  });

  test("typing after a Refine compares the refined draft with the new edits", async () => {
    stubFetch({ "POST /emails/c/refine": { body: refined } });
    const { result, rerender } = renderWorkflow(original);
    await refineTo(result);
    rerender(refined);
    act(() => result.current.setDraft("Thanks, I will reply by Monday."));
    expect(result.current.comparison).toEqual({
      before: "Thanks, I will reply by Friday.",
      after: "Thanks, I will reply by Monday.",
      source: "edits",
    });
  });

  test("a regenerate drops the Refine comparison", async () => {
    const regenerated = { ...original, draftReply: "Hi, noted with thanks." };
    stubFetch({
      "POST /emails/c/refine": { body: refined },
      "POST /emails/c/regenerate": { body: regenerated },
    });
    const { result, rerender } = renderWorkflow(original);
    await refineTo(result);
    rerender(refined);
    act(() => result.current.regenerate());
    await waitFor(() => expect(result.current.isRegenerating).toBe(false));
    rerender(regenerated);
    expect(result.current.comparison.source).toBe("edits");
  });

  test("a failed Refine leaves the comparison as it was", async () => {
    stubFetch({
      "POST /emails/c/refine": { status: 502, body: { error: { code: "agent_unavailable" } } },
    });
    const { result } = renderWorkflow(original);
    await act(async () => {
      await result.current.refine("Shorter").catch(() => undefined);
    });
    expect(result.current.comparison.source).toBe("edits");
  });
});

describe("saved reply templates", () => {
  const withDetails = emailFixture({
    id: "t",
    draftReply: "AI draft",
    details: [{ placeholder: "[PERSON_3]", value: "Aisyah Rahman", kind: "PERSON" }],
  });

  test("an inserted template shows the sender's real name, as the editor shows the stored draft", () => {
    const { result } = renderWorkflow(withDetails);
    act(() => result.current.insertTemplate("Hi [PERSON_3], thanks."));
    expect(result.current.draft).toBe("Hi Aisyah Rahman, thanks.");
    expect(result.current.hasUnsavedEdits).toBe(true);
  });

  test("a draft with an unfilled template blank cannot be sent until it is filled", () => {
    vi.useFakeTimers();
    const calls = stubFetch({ "POST /emails/t/send": { body: withDetails } });
    const { result } = renderWorkflow(withDetails);
    act(() => result.current.setDraft("Join at {{meeting link}}"));
    expect(result.current.unfilledBlanks).toEqual(["{{meeting link}}"]);
    act(() => result.current.send());
    expect(result.current.undoCountdown).toBeNull();
    act(() => result.current.setDraft("Join at https://meet.example/abc"));
    expect(result.current.unfilledBlanks).toEqual([]);
    act(() => result.current.send());
    expect(result.current.undoCountdown).not.toBeNull();
    expect(calls).toHaveLength(0);
    vi.useRealTimers();
  });

  test("drafting from a template asks the agent and drops the reader's typed text for its version", async () => {
    const adapted = { ...withDetails, draftReply: "Adapted for [PERSON_3]" };
    const calls = stubFetch({ "POST /templates/tpl-1/adapt": { body: adapted } });
    const { result, rerender } = renderWorkflow(withDetails);
    act(() => result.current.setDraft("Something I typed"));
    await act(async () => {
      await result.current.draftFromTemplate("tpl-1");
    });
    expect(calls[0].body).toEqual({ emailId: "t", tone: "professional" });
    rerender(adapted);
    expect(result.current.draft).toBe("Adapted for Aisyah Rahman");
  });
});
