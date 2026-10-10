import { HttpMethod, request } from "./client";

export type SourceType = "email" | "document";

export interface SearchSource {
  source_type: SourceType;
  id: string;
  title: string;
  subtitle: string;
  snippet: string;
  received_at: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: SearchSource[];
  has_restored_pii?: boolean;
}

export interface InboxSearchRequest {
  query: string;
  history?: Array<{ role: "user" | "assistant"; content: string }>;
  k_emails?: number;
  k_docs?: number;
}

export interface InboxSearchResponse {
  answer: string;
  sources: SearchSource[];
  sender_vault?: Record<string, string>;
  has_restored_pii?: boolean;
  intent?: string;
}

export async function searchInbox(req: InboxSearchRequest): Promise<InboxSearchResponse> {
  return request<InboxSearchResponse>("/api/search/inbox", {
    method: HttpMethod.Post,
    json: req,
  });
}
