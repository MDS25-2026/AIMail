import type { Email } from "../types/email";

/** Backend base URL. Defaults to the local backend; override with VITE_BACKEND_URL for other envs. */
const BASE = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";

/** Inbox list — Lane A fields + Lane B priority (no draft). */
export async function fetchEmails(): Promise<Email[]> {
  const res = await fetch(`${BASE}/emails`);
  if (!res.ok) throw new Error(`GET /emails failed (${res.status})`);
  return res.json();
}

/** One email with the Lane C draft/summary/critic filled in. */
export async function fetchEmail(id: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}`);
  if (!res.ok) throw new Error(`GET /emails/${id} failed (${res.status})`);
  return res.json();
}

/** Force a fresh draft in the given tone, replacing the cached one. */
export async function regenerateEmail(id: string, tone: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tone }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/regenerate failed (${res.status})`);
  return res.json();
}

/** Revise the current draft per a user instruction. */
export async function refineEmail(id: string, instruction: string, draft: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction, draft }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/refine failed (${res.status})`);
  return res.json();
}

/** Send the approved (possibly edited) draft as a reply; marks the email sent. */
export async function sendEmail(id: string, draft: string): Promise<Email> {
  const res = await fetch(`${BASE}/emails/${id}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft }),
  });
  if (!res.ok) throw new Error(`POST /emails/${id}/send failed (${res.status})`);
  return res.json();
}
