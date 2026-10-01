import type { Email, Translation } from "../types/email";
import type { PolicyDocument, SystemInfo } from "../types/knowledge";

/** Backend base URL. Defaults to the local backend; override with VITE_BACKEND_URL for other envs. */
export const BASE = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

/** Shared bearer token the backend requires on every route (backend/app/core/auth.py). */
const TOKEN = import.meta.env.VITE_BACKEND_API_TOKEN ?? "";

/** Auth header for backend calls; JSON senders spread it alongside Content-Type. */
function authHeaders(): Record<string, string> {
  return TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {};
}

/** Inbox list — Lane A fields + Lane B priority (no draft). */
export async function fetchEmails(): Promise<Email[]> {
  const res = await fetch(`${BASE}/emails`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`GET /emails failed (${res.status})`);
  return res.json();
}

/** One email with the Lane C draft/summary/critic filled in. */
export async function fetchEmail(id: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`GET /emails/${id} failed (${res.status})`);
  return res.json();
}

/** The model failed on this email's content (422 draft_refused); retrying cannot change that. */
export class DraftRefusedError extends Error {}

const DRAFT_REFUSED = "draft_refused";

async function regenerateError(res: Response, message: string): Promise<Error> {
  const body: unknown = await res.json().catch(() => null);
  const isRefused =
    typeof body === "object" && body !== null && "detail" in body && body.detail === DRAFT_REFUSED;
  return isRefused ? new DraftRefusedError(message) : new Error(message);
}

/** Force a fresh draft in the given tone, replacing the cached one. */
export async function regenerateEmail(id: string, tone: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ tone }),
  });
  if (!res.ok)
    throw await regenerateError(res, `POST /emails/${id}/regenerate failed (${res.status})`);
  return res.json();
}

/** Revise the current draft per a user instruction. */
export async function refineEmail(id: string, instruction: string, draft: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ instruction, draft }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/refine failed (${res.status})`);
  return res.json();
}

/** The masked body in another language. 422 means the translation failed its faithfulness checks. */
export async function translateEmail(id: string, language: string): Promise<Translation> {
  const res = await fetch(`${BASE}/emails/${id}/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ language }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/translate failed (${res.status})`);
  return res.json();
}

/** Send the approved (possibly edited) draft as a reply; marks the email sent. */
export async function sendEmail(id: string, draft: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ draft }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/send failed (${res.status})`);
  return res.json();
}

/** Knowledge base inventory — one row per ingested policy document. */
export async function fetchDocuments(): Promise<PolicyDocument[]> {
  const res = await fetch(`${BASE}/documents`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`GET /documents failed (${res.status})`);
  return res.json();
}

/** Ingest pasted text as a document; returns the number of chunks stored. */
export async function addDocument(title: string, text: string): Promise<number> {
  const res = await fetch(`${BASE}/documents`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
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
  const res = await fetch(`${BASE}/documents/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  if (!res.ok) throw uploadError(res);
  const body: { chunks: number } = await res.json();
  return body.chunks;
}

/** Turn the backend's guard responses into something a person can act on. */
/** Why an upload was refused, as a code the page translates; the page owns the wording. */
export type UploadFailure = "too_large" | "rate_limited" | "not_pdf" | "unauthorized" | "failed";

const UPLOAD_FAILURE_BY_STATUS: Record<number, UploadFailure> = {
  413: "too_large",
  429: "rate_limited",
  400: "not_pdf",
  401: "unauthorized",
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
  const res = await fetch(`${BASE}/system/info`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`GET /system/info failed (${res.status})`);
  return res.json();
}
