import type { Email, Translation } from "../types/email";
import type { PolicyDocument, SystemInfo } from "../types/knowledge";

/** Backend base URL. Defaults to the local backend; override with VITE_BACKEND_URL for other envs. */
export const BASE = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

/** Where "Sign in with Google" starts; the backend runs the flow and sets the session cookie. */
export const SIGN_IN_URL = `${BASE}/auth/google/start`;

// The backend refuses a cookie request that changes state without it (CSRF, ADR 0005).
const CLIENT_HEADER = { "X-AIMail-Client": "1" };

/** No session, or it expired. The app sends the reader to the sign-in page. */
export class SignedOutError extends Error {}

type ApiInit = Omit<RequestInit, "headers" | "credentials"> & { headers?: Record<string, string> };

function send(path: string, init: ApiInit): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { ...CLIENT_HEADER, ...init.headers },
  });
}

// Shared by every call that finds the session expired at once: a refresh token can be spent only
// once, so a second, parallel renewal would be refused and sign the reader out.
let renewing: Promise<boolean> | null = null;

/** Trade the refresh cookie for a new session (the access cookie lasts an hour, this one a week). */
function renewSession(): Promise<boolean> {
  renewing ??= send("/auth/session/refresh", { method: "POST" })
    .then((res) => res.ok)
    .finally(() => {
      renewing = null;
    });
  return renewing;
}

/**
 * A backend call carrying the HttpOnly session cookie; there is no token in the browser. An expired
 * session is renewed once and the call retried, so the reader is only asked to sign in again when
 * the refresh cookie is gone too.
 */
async function apiFetch(path: string, init: ApiInit = {}): Promise<Response> {
  const res = await send(path, init);
  if (res.status !== 401) return res;
  if (await renewSession()) {
    const retried = await send(path, init);
    if (retried.status !== 401) return retried;
  }
  throw new SignedOutError(`${init.method ?? "GET"} ${path} needs sign-in`);
}

export type SessionInfo = { email: string; hasMailbox: boolean };

/** Who is signed in, and whether a mailbox is connected to that account. */
export async function fetchSession(): Promise<SessionInfo> {
  const res = await apiFetch("/auth/session");
  if (!res.ok) throw new Error(`GET /auth/session failed (${res.status})`);
  return res.json();
}

/** End the session at Supabase and clear the cookies. */
export async function signOut(): Promise<void> {
  const res = await apiFetch("/auth/session", { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE /auth/session failed (${res.status})`);
}

/** Inbox list — Lane A fields + Lane B priority (no draft). */
export async function fetchEmails(): Promise<Email[]> {
  const res = await apiFetch(`/emails`);
  if (!res.ok) throw new Error(`GET /emails failed (${res.status})`);
  return res.json();
}

/** One email with the Lane C draft/summary/critic filled in. */
export async function fetchEmail(id: string): Promise<Email> {
  const res = await apiFetch(`/emails/${id}`);
  if (!res.ok) throw new Error(`GET /emails/${id} failed (${res.status})`);
  return res.json();
}

/** Stop AIMail reading the reader's Gmail and delete what it stored from it (Settings > Account). */
export async function disconnectGmail(): Promise<void> {
  const res = await apiFetch("/account/gmail", { method: "DELETE" });
  if (!res.ok) throw await apiError(res, `DELETE /account/gmail failed (${res.status})`);
}

/** Delete everything the reader has in AIMail, then their sign-in. Safe to try again. */
export async function deleteAccount(): Promise<void> {
  const res = await apiFetch("/account", { method: "DELETE" });
  if (!res.ok) throw await apiError(res, `DELETE /account failed (${res.status})`);
}

/** The newest of the reader's emails in a Gmail thread, or null when AIMail has none (extension). */
export async function fetchEmailByThread(threadId: string): Promise<Email | null> {
  const res = await apiFetch(`/emails/by-thread/${encodeURIComponent(threadId)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`GET /emails/by-thread failed (${res.status})`);
  return res.json();
}

/** The model failed on this email's content (422 draft_refused); retrying cannot change that. */
export class DraftRefusedError extends Error {}

/** Gmail may have sent the reply but the answer was lost (504 send_outcome_unknown). Never retry blind. */
export class SendOutcomeUnknownError extends Error {}

/** A placeholder in the reply has no value to fill in (422 unresolved_placeholders). */
export class UnresolvedPlaceholdersError extends Error {}

/** The owner let AIMail read their Gmail but not send from it (403 send_not_granted). */
export class SendNotGrantedError extends Error {}

const ERROR_BY_DETAIL: Record<string, new (message: string) => Error> = {
  draft_refused: DraftRefusedError,
  send_outcome_unknown: SendOutcomeUnknownError,
  send_not_granted: SendNotGrantedError,
  unresolved_placeholders: UnresolvedPlaceholdersError,
};

/** The typed error for a failed call, chosen by the backend's `detail` code. */
async function apiError(res: Response, message: string): Promise<Error> {
  const body: unknown = await res.json().catch(() => null);
  const detail =
    typeof body === "object" && body !== null && "detail" in body ? String(body.detail) : "";
  const ErrorType = ERROR_BY_DETAIL[detail] ?? Error;
  return new ErrorType(message);
}

/** Force a fresh draft in the given tone, replacing the cached one. */
export async function regenerateEmail(id: string, tone: string): Promise<Email> {
  const res = await apiFetch(`/emails/${id}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tone }),
  });
  if (!res.ok) throw await apiError(res, `POST /emails/${id}/regenerate failed (${res.status})`);
  return res.json();
}

/** Revise the current draft per a user instruction. */
export async function refineEmail(id: string, instruction: string, draft: string): Promise<Email> {
  const res = await apiFetch(`/emails/${id}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction, draft }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/refine failed (${res.status})`);
  return res.json();
}

/** The masked body in another language. 422 means the translation failed its faithfulness checks. */
export async function translateEmail(id: string, language: string): Promise<Translation> {
  const res = await apiFetch(`/emails/${id}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/translate failed (${res.status})`);
  return res.json();
}

/** Send the approved (possibly edited) draft as a reply; marks the email sent. */
export async function sendEmail(id: string, draft: string): Promise<Email> {
  const res = await apiFetch(`/emails/${id}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft }),
  });
  if (!res.ok) throw await apiError(res, `POST /emails/${id}/send failed (${res.status})`);
  return res.json();
}

/** Knowledge base inventory — one row per ingested policy document. */
export async function fetchDocuments(): Promise<PolicyDocument[]> {
  const res = await apiFetch(`/documents`);
  if (!res.ok) throw new Error(`GET /documents failed (${res.status})`);
  return res.json();
}

/** Ingest pasted text as a document; returns the number of chunks stored. */
export async function addDocument(title: string, text: string): Promise<number> {
  const res = await apiFetch(`/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, text }),
  });
  if (!res.ok) throw uploadError(res);
  const body: { chunks: number } = await res.json();
  return body.chunks;
}

/** Ingest a PDF; returns the number of chunks stored. */
export async function uploadDocument(file: File): Promise<number> {
  const form = new FormData();
  form.append("file", file);
  // No Content-Type: the browser sets the multipart boundary itself.
  const res = await apiFetch(`/documents/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw uploadError(res);
  const body: { chunks: number } = await res.json();
  return body.chunks;
}

/** Turn the backend's guard responses into something a person can act on. */
/** Why an upload was refused, as a code the page translates; the page owns the wording. */
export type UploadFailure = "too_large" | "rate_limited" | "not_pdf" | "failed";

const UPLOAD_FAILURE_BY_STATUS: Record<number, UploadFailure> = {
  413: "too_large",
  429: "rate_limited",
  400: "not_pdf",
};

export class UploadError extends Error {
  constructor(readonly failure: UploadFailure) {
    super(failure);
  }
}

function uploadError(res: Response): UploadError {
  return new UploadError(UPLOAD_FAILURE_BY_STATUS[res.status] ?? "failed");
}

/** Non-secret runtime configuration, for the Settings view. */
export async function fetchSystemInfo(): Promise<SystemInfo> {
  const res = await apiFetch(`/system/info`);
  if (!res.ok) throw new Error(`GET /system/info failed (${res.status})`);
  return res.json();
}

export type HoldingReplySettings = {
  enabled: boolean;
  activeWhen: "outside_hours" | "leave" | "always";
  workDays: number[];
  workStart: string;
  workEnd: string;
  timezone: string;
  leaveFrom: string | null;
  leaveUntil: string | null;
  audience: "correspondents" | "domain" | "everyone";
  scope: "needs_reply" | "all";
  cooldownDays: number;
  templates: Partial<Record<"en" | "ms" | "zh", string>>;
  defaultLanguage: "en" | "ms" | "zh";
};

export type HoldingReplyRecord = {
  id: string;
  emailId: string;
  recipient: string;
  language: string;
  scheduledFor: string;
  sentAt: string | null;
  cancelledReason: string | null;
  subject: string;
};

/** The settings were refused; `code` names the problem (specs/context/api-contracts.md). */
export class HoldingReplySettingsError extends Error {
  constructor(readonly code: string) {
    super(code);
  }
}

export async function fetchHoldingReplySettings(): Promise<HoldingReplySettings> {
  const res = await apiFetch("/settings/holding-reply");
  if (!res.ok) throw new Error(`GET /settings/holding-reply failed (${res.status})`);
  return res.json();
}

export async function saveHoldingReplySettings(
  settings: HoldingReplySettings,
): Promise<HoldingReplySettings> {
  const res = await apiFetch("/settings/holding-reply", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (res.status === 422) {
    const body: unknown = await res.json().catch(() => null);
    const detail =
      typeof body === "object" && body !== null && "detail" in body ? body.detail : null;
    throw new HoldingReplySettingsError(typeof detail === "string" ? detail : "invalid");
  }
  if (!res.ok) throw new Error(`PUT /settings/holding-reply failed (${res.status})`);
  return res.json();
}

export async function fetchHoldingReplies(): Promise<HoldingReplyRecord[]> {
  const res = await apiFetch("/holding-replies?limit=20");
  if (!res.ok) throw new Error(`GET /holding-replies failed (${res.status})`);
  return res.json();
}

export async function cancelHoldingReply(id: string): Promise<void> {
  const res = await apiFetch(`/holding-replies/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`DELETE /holding-replies failed (${res.status})`);
}
