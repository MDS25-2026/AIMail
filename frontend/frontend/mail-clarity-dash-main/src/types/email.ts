/**
 * Single source of truth for the email shape.
 * The ingestion / retrieval / generation lanes will eventually fill these in
 * for real — treat field names as fixed unless the team changes them together.
 */

export type Priority = "high" | "medium" | "low";
export type Tone = "professional" | "casual";

export type ThreadMessage = {
  sender: string;
  snippet: string;
};

export type Source = {
  /** The policy document's title. */
  label: string;
  chunkId?: string | null;
  /** The passage exactly as the model saw it when drafting. */
  excerpt?: string;
  /** Cosine similarity, 0-1. */
  score?: number | null;
};

export type Measure = { value: number; unit: string };

/** A quantity in the body, in both systems; the side matching `system` is as the sender wrote it. */
export type Quantity = {
  text: string;
  system: "metric" | "imperial";
  metric: Measure;
  imperial: Measure;
};

export type Translation = { language: string; text: string };

export type Email = {
  id: string;
  sender: string;
  subject: string;
  /** Short snippet for the inbox list. */
  preview: string;
  /** Full masked email body for the detail view. */
  body: string;
  /** ISO 8601 */
  timestamp: string;
  priority: Priority;
  threadContext: ThreadMessage[];
  aiSummary: string;
  actionItems: string[];
  draftReply: string;
  tone: Tone;
  sources: Source[];
  piiMasked: boolean;
  /** 0-1, from the Critic Agent's confidence pass. */
  criticConfidence: number;
  /** ISO 8601 when the approved reply was sent, else null/undefined. */
  sentAt?: string | null;
  /** Opened at least once. Anything new is unread. */
  isRead?: boolean;
  quantities?: Quantity[];
  /** Content withheld until personal data can be fully masked (#109). */
  maskingPending?: boolean;
};

/** Below this the draft is flagged "review recommended". */
export const CRITIC_CONFIDENCE_THRESHOLD = 0.8;
