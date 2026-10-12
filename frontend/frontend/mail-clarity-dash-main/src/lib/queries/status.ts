import { useQuery } from "@tanstack/react-query";

import { fetchServiceStatus } from "../api/status";
import { queryKeys } from "./keys";

// The server caches for 15 s; checking twice as often would only show the same answer.
const REFRESH_MS = 30_000;

/** Refreshes every 30 seconds while the tab is visible; React Query pauses it while hidden. */
export function useServiceStatus() {
  return useQuery({
    queryKey: queryKeys.serviceStatus,
    queryFn: fetchServiceStatus,
    refetchInterval: REFRESH_MS,
    retry: false,
  });
}
