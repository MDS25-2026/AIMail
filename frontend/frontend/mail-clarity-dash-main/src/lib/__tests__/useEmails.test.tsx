// @vitest-environment jsdom
import { act, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import { stubFetch } from "../../test/fetchStub";
import { renderHookWithProviders } from "../../test/render";
import { useEmail, useEmails, useMarkUnread } from "../queries";

test("older pages join the inbox after the newer ones, and the last page ends it", async () => {
  const pages = [
    { emails: [emailFixture({ id: "new" })], nextCursor: "c1" },
    { emails: [emailFixture({ id: "old" })], nextCursor: null },
  ];
  let served = 0;
  stubFetch({ "GET /emails": () => ({ body: pages[served++] }) });
  const { result } = renderHookWithProviders(() => useEmails(), { initialProps: undefined });

  await waitFor(() => expect(result.current.data?.map((email) => email.id)).toEqual(["new"]));
  expect(result.current.hasNextPage).toBe(true);
  await act(async () => {
    await result.current.fetchNextPage();
  });
  await waitFor(() =>
    expect(result.current.data?.map((email) => email.id)).toEqual(["new", "old"]),
  );
  expect(result.current.hasNextPage).toBe(false);
});

test("mark unread shows in the list at once, and refreshing the open email keeps it unread", async () => {
  const opened = emailFixture({ id: "e1", isRead: true });
  const urls: string[] = [];
  stubFetch({
    "GET /emails": { body: { emails: [opened], nextCursor: null } },
    "POST /emails/e1/unread": { status: 204 },
    "GET /emails/e1": { body: { ...opened, isRead: false } },
  });
  const fetchSpy = vi.mocked(fetch);
  const { result } = renderHookWithProviders(
    () => ({ inbox: useEmails(), markUnread: useMarkUnread(), open: useEmail("e1", true) }),
    { initialProps: undefined },
  );
  await waitFor(() => expect(result.current.inbox.data?.[0].isRead).toBe(true));
  await act(async () => {
    await result.current.markUnread.mutateAsync("e1");
  });
  await waitFor(() => expect(result.current.inbox.data?.[0].isRead).toBe(false));
  urls.push(...fetchSpy.mock.calls.map(([url]) => String(url)));
  // The open view is fetched without marking it read again.
  expect(urls.some((url) => url.endsWith("/emails/e1?markRead=false"))).toBe(true);
});
