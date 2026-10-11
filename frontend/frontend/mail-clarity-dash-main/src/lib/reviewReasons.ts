import type { TFunction } from "i18next";

import { ReviewCode, type ReviewReason } from "../types/email";

const KNOWN_CODES: ReadonlySet<string> = new Set(Object.values(ReviewCode));
const PII_KINDS = ["EMAIL_ADDRESS", "CREDIT_CARD", "IBAN_CODE", "MY_NRIC", "MY_PHONE"] as const;
type PiiKind = (typeof PII_KINDS)[number];
const isPiiKind = (kind: string): kind is PiiKind =>
  (PII_KINDS as readonly string[]).includes(kind);

// PII reasons carry entity types, never the matched text; each is named, not shown as a code.
function piiKinds(items: string[], t: TFunction): string {
  return items.map((kind) => t(`review.kinds.${isPiiKind(kind) ? kind : "other"}`)).join(", ");
}

/** One reason in the reader's language. A code from a newer agent reads as "flagged for review". */
export function reviewReasonText({ code, items = [] }: ReviewReason, t: TFunction): string {
  const known = KNOWN_CODES.has(code) ? code : ReviewCode.Unknown;
  const listed = known === ReviewCode.PiiFound ? piiKinds(items, t) : items.join(", ");
  return t(`review.reasons.${known}`, { items: listed });
}
