import type { AdminIdentity, AuditEvent, FlaggedDraft, Overview } from "../types/admin";
import { BACKEND_URL } from "./api/config";
import { ApiError, apiErrorFrom } from "./api/errors";

/**
 * The admin console API (docs/adr/0004). The session is an HttpOnly cookie the backend sets, so
 * this code never sees a token: it only sends the cookie along (credentials: "include") and the
 * header that marks a state-changing call as deliberate.
 */

const ADMIN_HEADER = { "X-AIMail-Admin": "1" };
const UNAUTHORIZED = 401;
const FORBIDDEN = 403;
const MAX_RETRIES = 2;

/** React Query retry policy for admin calls: transient failures retry, auth failures never do. */
export function retryUnlessAuth(failureCount: number, error: unknown): boolean {
  return !isAuthError(error) && failureCount < MAX_RETRIES;
}

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`${BACKEND_URL}/admin${path}`, { ...init, credentials: "include" });
}

// Refresh tokens are single-use at Supabase: three panels expiring together must share one
// refresh, or the second and third would present a token the first already spent.
let refreshing: Promise<boolean> | null = null;

function refreshOnce(): Promise<boolean> {
  refreshing ??= send("/session/refresh", { method: "POST", headers: ADMIN_HEADER })
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });
  return refreshing;
}

/** True for an error that means "not signed in as an admin": retrying cannot fix it. */
export function isAuthError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === UNAUTHORIZED || error.status === FORBIDDEN);
}

/** An expired access cookie is renewed once from the refresh cookie before giving up. */
async function getJson<T>(path: string): Promise<T> {
  let res = await send(path);
  if (res.status === UNAUTHORIZED && (await refreshOnce())) res = await send(path);
  if (!res.ok) throw await apiErrorFrom(res, `GET /admin${path.split("?")[0]}`);
  return res.json();
}

export const fetchAdminSession = () => getJson<AdminIdentity>("/session");
export const fetchOverview = (days: number) => getJson<Overview>(`/overview?days=${days}`);
export const fetchFlagged = () => getJson<FlaggedDraft[]>("/flagged");
export const fetchAudit = (failuresOnly: boolean) =>
  getJson<AuditEvent[]>(`/audit?limit=100&failures_only=${failuresOnly}`);

export async function signIn(email: string, password: string): Promise<AdminIdentity> {
  const res = await send("/session", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...ADMIN_HEADER },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw await apiErrorFrom(res, "POST /admin/session");
  return res.json();
}

export async function signOut(): Promise<void> {
  const res = await send("/session", { method: "DELETE", headers: ADMIN_HEADER });
  if (!res.ok) throw await apiErrorFrom(res, "DELETE /admin/session");
}
