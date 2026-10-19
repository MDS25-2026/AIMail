import { useQuery } from "@tanstack/react-query";

import { fetchAuditTrail } from "../api/audit";
import { queryKeys } from "./keys";

export function useAuditTrail(limit = 50) {
  return useQuery({
    queryKey: [...queryKeys.auditTrail, limit],
    queryFn: () => fetchAuditTrail(limit),
  });
}
