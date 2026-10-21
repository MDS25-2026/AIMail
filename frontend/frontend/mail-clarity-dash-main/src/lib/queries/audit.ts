import { keepPreviousData, useQuery } from "@tanstack/react-query";

import type { AuditFilters } from "../../types/audit";
import { fetchAuditTrail } from "../api/audit";
import { queryKeys } from "./keys";

/** The last answer stays on screen while a new filter loads, so the list does not blank out. */
export function useAuditTrail(filters: AuditFilters, limit: number) {
  return useQuery({
    queryKey: [...queryKeys.auditTrail, filters, limit],
    queryFn: () => fetchAuditTrail(filters, limit),
    placeholderData: keepPreviousData,
  });
}
