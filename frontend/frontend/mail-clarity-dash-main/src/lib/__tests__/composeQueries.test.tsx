// @vitest-environment jsdom
import { act, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { stubFetch, type StubCall } from "../../test/fetchStub";
import { renderHookWithProviders } from "../../test/render";
import { ComposeState, type ComposeDraft } from "../../types/compose";
import { SENDING_POLL_MS, useComposeDraftQuery } from "../queries";

function composeDraft(state: ComposeState): ComposeDraft {
  return {
    id: "d1",
    to: ["a@x.com"],
    cc: [],
    subject: "Hi",
    brief: "",
    body: "Hello",
    tone: "professional",
    state,
    updatedAt: "2026-10-21T09:00:00Z",
  };
}

const reads = (calls: StubCall[]) => calls.filter((call) => call.path === "/compose/d1");

afterEach(() => vi.useRealTimers());

test("a draft being sent is asked about again until it is no longer sending", async () => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
  const answers = [ComposeState.Sending, ComposeState.Sending, ComposeState.OutcomeUnknown];
  const calls = stubFetch({
    "GET /compose/d1": () => ({
      body: composeDraft(answers.shift() ?? ComposeState.OutcomeUnknown),
    }),
  });
  const { result } = renderHookWithProviders(() => useComposeDraftQuery("d1"));
  await act(() => vi.advanceTimersByTimeAsync(100));
  expect(result.current.data?.state).toBe(ComposeState.Sending);

  await act(() => vi.advanceTimersByTimeAsync(SENDING_POLL_MS));
  expect(reads(calls)).toHaveLength(2);
  await act(() => vi.advanceTimersByTimeAsync(SENDING_POLL_MS));
  expect(reads(calls)).toHaveLength(3);
  expect(result.current.data?.state).toBe(ComposeState.OutcomeUnknown);

  // Any other state stops the polling.
  await act(() => vi.advanceTimersByTimeAsync(SENDING_POLL_MS * 3));
  expect(reads(calls)).toHaveLength(3);
});

test("a draft that is not being sent is not polled", async () => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
  const calls = stubFetch({ "GET /compose/d1": { body: composeDraft(ComposeState.Draft) } });
  renderHookWithProviders(() => useComposeDraftQuery("d1"));
  await act(() => vi.advanceTimersByTimeAsync(SENDING_POLL_MS * 2));
  vi.useRealTimers();
  await waitFor(() => expect(reads(calls)).toHaveLength(1));
});
