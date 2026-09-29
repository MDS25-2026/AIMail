/** Mirrors backend/app/admin/schemas.py. Aggregates and ids only: no email content. */

export type Count = { label: string; count: number };

export type Overview = {
  days: number;
  mailbox: {
    total: number;
    masking_pending: number;
    generated: number;
    awaiting_review: number;
    sent: number;
    unread: number;
  };
  privacy: {
    quarantined: number;
    released: number;
    degraded_before_fix: number;
    attachment_text_dropped: number;
    pages_withheld: number;
    attachment_failures: number;
  };
  review_reasons: Count[];
  models: {
    drafts: number;
    attempts: number;
    outcomes: Count[];
    drafts_using_fallback: number;
    model_ms_p50: number | null;
    model_ms_p95: number | null;
  };
};

export type AuditEvent = {
  created_at: string;
  action: string;
  success: boolean | null;
  detail: string;
};

export type FlaggedDraft = {
  id: string;
  subject: string;
  generated_at: string | null;
  confidence: number | null;
  attempts: number | null;
  reasons: string[];
};

export type AdminIdentity = { email: string };
