import type { AuditTrail } from "../../types/audit";
import { request } from "./client";

/** The signed-in user's audit rows, and whether the whole SHA-256 hash chain is intact (#148). */
export const fetchAuditTrail = (limit = 50) => request<AuditTrail>(`/audit?limit=${limit}`);
