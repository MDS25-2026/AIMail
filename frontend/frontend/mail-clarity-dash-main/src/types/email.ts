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
  /** Pre-formatted for display, e.g. "Past emails (8)". */
  label: string;
};

export type Email = {
  id: string;
  sender: string;
  subject: string;
  preview: string;
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
};

/** Below this the draft is flagged "review recommended". */
export const CRITIC_CONFIDENCE_THRESHOLD = 0.8;
