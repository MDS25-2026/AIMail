import type { InfiniteData, QueryClient } from "@tanstack/react-query";

import type { EmailPage } from "../../types/email";
import { fetchEmailPage } from "../api/emails";
import { queryKeys } from "./keys";

type Inbox = InfiniteData<EmailPage, string | undefined>;

/** Every loaded page again: a resync, a reopened stream, or a change page 1 alone cannot show. */
export function invalidateInbox(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: queryKeys.emails });
}

/**
 * Refetches page 1 alone when the changed emails can only be there, instead of every loaded page.
 * Pages are keyset (the server's cursor is page 1's last row), so swapping in a fresh page 1 is
 * only safe while it still ends on the same row: a new email or a removed one shifts that edge,
 * and the row pushed across it would vanish or show twice. Anything else refetches every page.
 */
export async function refreshChangedEmails(
  queryClient: QueryClient,
  changedIds: ReadonlySet<string>,
): Promise<void> {
  if (firstPageOnly(queryClient, changedIds) === null) return invalidateInbox(queryClient);
  // A failed page 1 hands over to the full refetch, whose query then shows its own error.
  const fresh = await fetchEmailPage().catch(() => null);
  const inbox = firstPageOnly(queryClient, changedIds);
  if (fresh === null || inbox === null || fresh.nextCursor !== inbox.pages[0].nextCursor) {
    return invalidateInbox(queryClient);
  }
  queryClient.setQueryData<Inbox>(queryKeys.emails, {
    ...inbox,
    pages: [fresh, ...inbox.pages.slice(1)],
  });
}

/** The cached inbox when page 1 alone may be refreshed; null when every page must be. */
function firstPageOnly(queryClient: QueryClient, changedIds: ReadonlySet<string>): Inbox | null {
  const inbox = queryClient.getQueryData<Inbox>(queryKeys.emails);
  const query = queryClient.getQueryCache().find({ queryKey: queryKeys.emails, exact: true });
  // One page: a plain refetch is already one call. Unwatched: invalidating only marks it stale.
  if (inbox === undefined || inbox.pages.length < 2 || !query?.isActive()) return null;
  if (queryClient.isFetching({ queryKey: queryKeys.emails }) > 0) return null;
  const isOnLaterPage = inbox.pages
    .slice(1)
    .some((page) => page.emails.some((email) => changedIds.has(email.id)));
  return isOnLaterPage ? null : inbox;
}
