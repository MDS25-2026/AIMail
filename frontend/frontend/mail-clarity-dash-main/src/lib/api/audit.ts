import {
  AuditWindow,
  NO_AUDIT_FILTERS,
  type AuditFilters,
  type AuditTrail,
} from "../../types/audit";
import { request } from "./client";

/** Everyone's audit rows for an admin, and whether the whole SHA-256 hash chain is intact (#148). */
export function fetchAuditTrail(
  filters: AuditFilters = NO_AUDIT_FILTERS,
  limit = 50,
): Promise<AuditTrail> {
  const query = new URLSearchParams({ limit: String(limit) });
  // Only the filters in use are sent, so the backend's defaults stay the one source of "any".
  if (filters.group) query.set("group", filters.group);
  if (filters.person) query.set("person", filters.person);
  if (filters.isFailuresOnly) query.set("failures_only", "true");
  if (filters.window !== AuditWindow.All) query.set("window", filters.window);
  return request<AuditTrail>(`/audit?${query}`);
}
