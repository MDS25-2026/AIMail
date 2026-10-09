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
