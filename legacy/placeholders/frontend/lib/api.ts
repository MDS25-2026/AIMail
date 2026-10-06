import type { AnswerResponse, ContextChunk, DocumentSummary } from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function search(query: string, k = 5): Promise<ContextChunk[]> {
  const res = await fetch(`${BASE}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, k }),
  });
  if (!res.ok) throw new Error(`Search failed (HTTP ${res.status})`);
  return res.json();
}

export async function ask(question: string, k = 5): Promise<AnswerResponse> {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, k }),
  });
  if (!res.ok) throw new Error(`Ask failed (HTTP ${res.status})`);
  return res.json();
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${BASE}/documents`);
  if (!res.ok) throw new Error(`Could not load knowledge base (HTTP ${res.status})`);
  return res.json();
}

export async function uploadPdf(file: File): Promise<number> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${BASE}/documents/upload`, { method: "POST", body });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(detail?.detail ?? `Upload failed (HTTP ${res.status})`);
  }
  const data = (await res.json()) as { chunks: number };
  return data.chunks;
}
