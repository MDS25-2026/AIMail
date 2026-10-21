// @vitest-environment jsdom
import { act } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi, type MockInstance } from "vitest";

import { startDemo, leaveDemo } from "../../demo/mode";
import { renderHookWithProviders, testQueryClient } from "../../test/render";
import { BACKEND_URL } from "../api/config";
import { queryKeys } from "../queries/keys";
import {
  COALESCE_MS,
  FAILURES_BEFORE_POLLING,
  FALLBACK_POLL_MS,
  useMailboxEvents,
} from "../queries/events";

/** The browser's EventSource, driven by hand: jsdom has none. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  isClosed = false;
  private readonly listeners = new Map<string, (event: Event) => void>();

  constructor(
    readonly url: string,
    readonly init?: EventSourceInit,
  ) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(name: string, listener: (event: Event) => void) {
    this.listeners.set(name, listener);
  }

  close() {
    this.isClosed = true;
  }

  emit(name: string, data: string) {
    this.listeners.get(name)?.(new MessageEvent(name, { data }));
  }
}

const SESSION = { email: "owner@example.com", hasMailbox: true, needsReconnect: false };

function signedInClient() {
  const client = testQueryClient();
  client.setQueryData(queryKeys.session, SESSION);
  return client;
}

type Invalidate = MockInstance<ReturnType<typeof testQueryClient>["invalidateQueries"]>;

function keysInvalidated(spy: Invalidate) {
  return spy.mock.calls.map(([filters]) => (filters?.queryKey ?? []).join("/"));
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.useFakeTimers();
});

afterEach(() => {
  leaveDemo();
  vi.useRealTimers();
});

test("opens one stream at the backend with the session cookie, and refetches when it opens", () => {
  const client = signedInClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const { result } = renderHookWithProviders(() => useMailboxEvents({ isEnabled: true }), {
    client,
  });

  expect(FakeEventSource.instances).toHaveLength(1);
  const source = FakeEventSource.instances[0];
  expect(source.url).toBe(`${BACKEND_URL}/events`);
  expect(source.init?.withCredentials).toBe(true);

  act(() => source.onopen?.());
  expect(result.current).toBe("live");
  act(() => vi.advanceTimersByTime(COALESCE_MS));
  expect(keysInvalidated(invalidate)).toEqual(["emails", "todo"]);
});

test("a burst of new-mail events refetches the inbox once", () => {
  const client = signedInClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  renderHookWithProviders(() => useMailboxEvents({ isEnabled: true }), { client });
  const source = FakeEventSource.instances[0];

  act(() => {
    for (let index = 0; index < 5; index += 1) {
      source.emit("mailbox", JSON.stringify({ kind: "new", messageId: `m${index}` }));
    }
    vi.advanceTimersByTime(COALESCE_MS);
  });
  expect(keysInvalidated(invalidate)).toEqual(["emails", "todo"]);
});

test("a finished draft also refreshes that email, so the editor fills without polling", () => {
  const client = signedInClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  renderHookWithProviders(() => useMailboxEvents({ isEnabled: true }), { client });

  act(() => {
    FakeEventSource.instances[0].emit(
      "mailbox",
      JSON.stringify({ kind: "draft", messageId: "e7" }),
    );
    vi.advanceTimersByTime(COALESCE_MS);
  });
  expect(keysInvalidated(invalidate)).toEqual(["email/e7", "emails", "todo"]);
});

test("an event that is not the backend's shape is ignored", () => {
  const client = signedInClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  renderHookWithProviders(() => useMailboxEvents({ isEnabled: true }), { client });

  act(() => {
    const source = FakeEventSource.instances[0];
    source.emit("mailbox", "not json");
    source.emit("mailbox", JSON.stringify({ kind: "body", messageId: "e1" }));
    vi.advanceTimersByTime(COALESCE_MS);
  });
  expect(invalidate).not.toHaveBeenCalled();
});

test("after three drops the inbox polls every minute until the stream is back", () => {
  const client = signedInClient();
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const { result } = renderHookWithProviders(() => useMailboxEvents({ isEnabled: true }), {
    client,
  });
  const source = FakeEventSource.instances[0];

  act(() => {
    for (let index = 0; index < FAILURES_BEFORE_POLLING; index += 1) source.onerror?.();
  });
  expect(result.current).toBe("reconnecting");
  act(() => vi.advanceTimersByTime(FALLBACK_POLL_MS * 2));
  expect(keysInvalidated(invalidate)).toEqual(["emails", "todo", "emails", "todo"]);

  act(() => source.onopen?.());
  invalidate.mockClear();
  act(() => vi.advanceTimersByTime(FALLBACK_POLL_MS * 2));
  expect(keysInvalidated(invalidate)).toEqual(["emails", "todo"]); // the open's own refetch only
});

test("the demo opens no stream", () => {
  startDemo();
  const { result } = renderHookWithProviders(() => useMailboxEvents({ isEnabled: true }), {
    client: signedInClient(),
  });
  expect(FakeEventSource.instances).toHaveLength(0);
  expect(result.current).toBe("off");
});

test("a signed-out page opens no stream", () => {
  renderHookWithProviders(() => useMailboxEvents({ isEnabled: true }), {
    client: testQueryClient(),
  });
  expect(FakeEventSource.instances).toHaveLength(0);
});

test("a page that does not want the stream opens none", () => {
  const { result } = renderHookWithProviders(() => useMailboxEvents({ isEnabled: false }), {
    client: signedInClient(),
  });
  expect(FakeEventSource.instances).toHaveLength(0);
  expect(result.current).toBe("off");
});

test("moving to a page without the stream closes it and shows nothing", () => {
  const { result, rerender } = renderHookWithProviders(
    ({ isEnabled }: { isEnabled: boolean }) => useMailboxEvents({ isEnabled }),
    { client: signedInClient(), initialProps: { isEnabled: true } },
  );
  act(() => FakeEventSource.instances[0].onopen?.());
  rerender({ isEnabled: false });
  expect(FakeEventSource.instances[0].isClosed).toBe(true);
  expect(result.current).toBe("off");
});

test("leaving the page closes the stream", () => {
  const { unmount } = renderHookWithProviders(() => useMailboxEvents({ isEnabled: true }), {
    client: signedInClient(),
  });
  unmount();
  expect(FakeEventSource.instances[0].isClosed).toBe(true);
});
