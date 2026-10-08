// @vitest-environment jsdom
import { act, waitFor } from "@testing-library/react";
import { describe, expect, test } from "vitest";

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

  test("sending anyway sends the draft as it is at that moment", async () => {
    const calls = stubFetch({ "POST /emails/m/send": { body: { ...marked, sentAt: "now" } } });
    const { result } = renderWorkflow(marked);
    act(() => result.current.send());
    act(() => result.current.setDraft("Dear [Redacted], thanks again."));
    act(() => result.current.status.onConfirm());
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
