/**
 * Shapes for the knowledge base and system views.
 * Mirrors backend/app/main.py — change both together, and record it in
 * specs/context/api-contracts.md.
 */

export type PolicyDocument = {
  document_id: string;
  title: string;
  source: string;
  doc_type: string;
  chunk_count: number;
};

export type SystemInfo = {
  chat_model: string;
  embedding_model: string;
  embedding_dim: number;
  priority_model: string;
  auth_enabled: boolean;
  auto_generate: boolean;
  generate_poll_seconds: number;
  document_count: number;
  chunk_count: number;
};
