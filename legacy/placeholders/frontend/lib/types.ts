export interface ContextChunk {
  chunk_id: string;
  content: string;
  similarity_score: number;
  source_title: string;
}

export interface DocumentSummary {
  document_id: string;
  title: string;
  source: string;
  doc_type: string;
  chunk_count: number;
}

export interface AnswerResponse {
  answer: string;
  sources: ContextChunk[];
}
