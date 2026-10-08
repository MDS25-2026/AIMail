// @vitest-environment jsdom
import { act, waitFor } from "@testing-library/react";
import { expect, test } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import { stubFetch } from "../../test/fetchStub";
import { renderHookWithProviders } from "../../test/render";
import { useEmails } from "../queries";

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
