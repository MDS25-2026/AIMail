import { AuthStatus, MaskingStatus, type Email } from "../types/email";

/** A complete, masked, verified email; override only what a test is about. */
export function emailFixture(overrides: Partial<Email> = {}): Email {
  return {
    id: "email-1",
    sender: "Aisyah <aisyah@example.com>",
    subject: "Invoice question",
    preview: "Could you confirm the invoice date?",
    body: "Could you confirm the invoice date?",
    timestamp: "2026-10-08T09:00:00Z",
    priority: "medium",
    threadContext: [],
    aiSummary: "Asks to confirm an invoice date.",
    actionItems: [],
    draftReply: "Thanks, the invoice is dated 1 October.",
    tone: "professional",
    sources: [],
    piiMasked: true,
    criticConfidence: 0.9,
    masking: MaskingStatus.Complete,
    authStatus: AuthStatus.Pass,
    ...overrides,
  };
}
