import type { DocumentDetail, PolicyDocument } from "../../types/knowledge";
import { HttpMethod, request } from "./client";

type Ingested = { chunks: number };

/** Knowledge base inventory: one row per ingested policy document. */
export const fetchDocuments = () => request<PolicyDocument[]>("/documents");

/** Fetch full document detail including reassembled text and ordered chunks. */
export const fetchDocument = (documentId: string) =>
  request<DocumentDetail>(`/documents/${encodeURIComponent(documentId)}`);

/** Remove a document and everything stored for it; drafts stop citing it at once. */
export const deleteDocument = (documentId: string) =>
  request<void>(`/documents/${encodeURIComponent(documentId)}`, { method: HttpMethod.Delete });

/** Ingest pasted text as a document; returns the number of chunks stored. */
export async function addDocument(title: string, text: string): Promise<number> {
  const body = await request<Ingested>("/documents", {
    method: HttpMethod.Post,
    json: { title, text },
  });
  return body.chunks;
}

/** Ingest a PDF; returns the number of chunks stored. */
export async function uploadDocument(file: File): Promise<number> {
  const form = new FormData();
  form.append("file", file);
  const body = await request<Ingested>("/documents/upload", { method: HttpMethod.Post, form });
  return body.chunks;
}
