import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { isSignedOut } from "../api/errors";

const MAX_RETRIES = 3;
// Every action updates or invalidates its own entries; this only spares a refetch per remount.
const STALE_MS = 30_000;

type QueryClientOptions = { onSignedOut?: () => void };

/** The one client setup for router and extension; a signed-out call is never retried. */
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
