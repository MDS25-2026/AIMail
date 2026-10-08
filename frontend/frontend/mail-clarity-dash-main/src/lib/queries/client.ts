import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { isSignedOut } from "../api/errors";

const MAX_RETRIES = 3;
// Most of what the dashboard shows changes only when the reader acts, and every action updates
// or invalidates its own entries; this only spares refetching on every remount.
const STALE_MS = 30_000;

type QueryClientOptions = { onSignedOut?: () => void };

/**
 * The one query client setup, for the dashboard router and the extension panel alike. A call
 * that finds the session gone is never retried and is reported once through `onSignedOut`.
 */
export function createQueryClient({ onSignedOut }: QueryClientOptions = {}): QueryClient {
  const report = (error: unknown) => {
    if (isSignedOut(error)) onSignedOut?.();
  };
  return new QueryClient({
    queryCache: new QueryCache({ onError: report }),
    mutationCache: new MutationCache({ onError: report }),
    defaultOptions: {
      queries: {
        staleTime: STALE_MS,
        retry: (failures, error) => !isSignedOut(error) && failures < MAX_RETRIES,
      },
    },
  });
}
