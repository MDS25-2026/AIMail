// @vitest-environment jsdom
import { act, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import { LiveInboxContext } from "../liveInbox";
import { DRAFT_POLL_MS, LIVE_DRAFT_POLL_MS, useEmail, type LiveState } from "../queries";

afterEach(() => {
  vi.useRealTimers();
});

async function detailFetchesAfter(live: LiveState, waitMs: number): Promise<number> {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const calls = stubFetch({
    "GET /emails/e1": { body: emailFixture({ id: "e1", isDrafting: true }) },
  });
  let isDrafting: boolean | undefined;
  function OpenEmail() {
    isDrafting = useEmail("e1").data?.isDrafting;
    return null;
  }
  renderWithProviders(
    <LiveInboxContext.Provider value={live}>
      <OpenEmail />
    </LiveInboxContext.Provider>,
  );
  await waitFor(() => expect(isDrafting).toBe(true));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(waitMs);
  });
  return calls.length;
}

test("while drafting with the stream down, the open email is polled on the short beat", async () => {
  expect(await detailFetchesAfter("reconnecting", DRAFT_POLL_MS * 2)).toBeGreaterThanOrEqual(3);
});

test("while drafting with the stream live, the short beat does not poll", async () => {
  expect(await detailFetchesAfter("live", DRAFT_POLL_MS * 2)).toBe(1);
});

test("while drafting with the stream live, the slow beat still ends a failed draft", async () => {
  expect(await detailFetchesAfter("live", LIVE_DRAFT_POLL_MS)).toBe(2);
});
