// @vitest-environment jsdom
import { act, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import { renderHookWithProviders } from "../../test/render";
import type { EmailPage } from "../../types/email";
import { useEmails } from "../queries";
import { refreshChangedEmails } from "../queries/inboxRefresh";

const OLDER = "?cursor=c1";
const pageResponse = (page: EmailPage) => new Response(JSON.stringify(page));

/** GET /emails by its query string (the shared stub sees paths only); "" is page 1. */
function stubInbox(answer: (query: string) => EmailPage): string[] {
  const queries: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const { pathname, search } = new URL(url);
      expect(pathname).toBe("/emails");
      queries.push(search || "page 1");
      return pageResponse(answer(search));
    }),
  );
  return queries;
}

/** Two pages loaded; `firstPage` is page 1 from the next call on, and any cursor gets page 2. */
async function twoPagesLoaded(firstPage: () => EmailPage) {
  let isLoaded = false;
  const calls = stubInbox((query) => {
    if (query.startsWith("?cursor="))
      return { emails: [emailFixture({ id: "b1" })], nextCursor: null };
    if (isLoaded) return firstPage();
    return { emails: [emailFixture({ id: "a1", isRead: false })], nextCursor: "c1" };
  });
  const rendered = renderHookWithProviders(() => useEmails(), { initialProps: undefined });
  await waitFor(() => expect(rendered.result.current.data).toHaveLength(1));
  await act(async () => {
    await rendered.result.current.fetchNextPage();
  });
  await waitFor(() => expect(rendered.result.current.data).toHaveLength(2));
  isLoaded = true;
  calls.length = 0;
  return { ...rendered, calls };
}

test("a change to an email on page 1 refetches page 1 alone and keeps the older pages", async () => {
  const { result, client, calls } = await twoPagesLoaded(() => ({
    emails: [emailFixture({ id: "a1", isRead: true })],
    nextCursor: "c1",
  }));
  await act(() => refreshChangedEmails(client, new Set(["a1"])));
  expect(calls).toEqual(["page 1"]);
  await waitFor(() =>
    expect(result.current.data?.map((email) => [email.id, email.isRead])).toEqual([
      ["a1", true],
      ["b1", true],
    ]),
  );
});

test("new mail that moves page 1's last row refetches every page, so that row is not lost", async () => {
  const { result, client, calls } = await twoPagesLoaded(() => ({
    emails: [emailFixture({ id: "n1" })],
    nextCursor: "c0",
  }));
  await act(() => refreshChangedEmails(client, new Set(["n1"])));
  await waitFor(() => expect(calls).toEqual(["page 1", "page 1", "?cursor=c0"]));
  await waitFor(() => expect(result.current.data?.map((email) => email.id)).toEqual(["n1", "b1"]));
});

test("a change to an email on an older page refetches every page", async () => {
  const { client, calls } = await twoPagesLoaded(() => ({
    emails: [emailFixture({ id: "a1" })],
    nextCursor: "c1",
  }));
  await act(() => refreshChangedEmails(client, new Set(["b1"])));
  await waitFor(() => expect(calls).toEqual(["page 1", OLDER]));
});

test("with one page loaded, the change is a plain refetch of that page", async () => {
  const calls = stubInbox(() => ({ emails: [emailFixture({ id: "a1" })], nextCursor: null }));
  const { result, client } = renderHookWithProviders(() => useEmails(), {
    initialProps: undefined,
  });
  await waitFor(() => expect(result.current.data).toHaveLength(1));
  calls.length = 0;
  await act(() => refreshChangedEmails(client, new Set(["a1"])));
  await waitFor(() => expect(calls).toEqual(["page 1"]));
});
