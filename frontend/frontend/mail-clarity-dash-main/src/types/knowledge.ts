/** Shapes for the knowledge base and system views, from the backend's schema. */
import type { Schemas } from "./schema";

export type PolicyDocument = Schemas["DocumentSummary"];

export interface ChunkDetail {
  id: string;
  chunk_idx: number;
  section: string | null;
  content: string;
}

export interface DocumentDetail {
  document_id: string;
  title: string;
  source: string;
  doc_type: string;
  chunk_count: number;
  content: string;
  chunks: ChunkDetail[];
}

export type SystemInfo = Schemas["SystemInfo"];
