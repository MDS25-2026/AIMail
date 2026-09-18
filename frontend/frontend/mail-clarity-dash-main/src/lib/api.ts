import type { Email } from "../types/email";
import type { PolicyDocument, SystemInfo } from "../types/knowledge";

/** Backend base URL. Defaults to the local backend; override with VITE_BACKEND_URL for other envs. */
const BASE = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

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

/** Force a fresh draft in the given tone, replacing the cached one. */
export async function regenerateEmail(id: string, tone: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ tone }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/regenerate failed (${res.status})`);
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
  if (!res.ok) throw new Error(await uploadErrorMessage(res, "POST /documents"));
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
  if (!res.ok) throw new Error(await uploadErrorMessage(res, "POST /documents/upload"));
  const body: { chunks: number } = await res.json();
  return body.chunks;
}

/** Turn the backend's guard responses into something a person can act on. */
async function uploadErrorMessage(res: Response, route: string): Promise<string> {
  if (res.status === 413) return "That file is over the 10 MB limit.";
  if (res.status === 429) return "Too many uploads just now — wait a minute and retry.";
  if (res.status === 400) return "That file was rejected: it must be a real PDF.";
  if (res.status === 401) return "Not authorised — check VITE_BACKEND_API_TOKEN.";
  return `${route} failed (${res.status})`;
}

/** Non-secret runtime configuration, for the Settings view. */
export async function fetchSystemInfo(): Promise<SystemInfo> {
  const res = await fetch(`${BASE}/system/info`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`GET /system/info failed (${res.status})`);
  return res.json();
}
