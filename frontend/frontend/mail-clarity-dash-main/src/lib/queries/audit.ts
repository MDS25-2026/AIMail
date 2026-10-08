import { useQuery } from "@tanstack/react-query";

import { fetchAuditTrail } from "../api/audit";
import { queryKeys } from "./keys";

export function useAuditTrail() {
  return useQuery({ queryKey: queryKeys.auditTrail, queryFn: fetchAuditTrail });
}
