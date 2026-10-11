import type { TFunction } from "i18next";

import type { AuditFields, AuditTrailEvent } from "../types/audit";

// Actions with a translated name; any other is shown as its code, which is the honest fallback.
const NAMED_ACTIONS = [
  "generate_draft",
  "refine_draft",
  "approve_and_send",
  "follow_up_sent",
  "send_outcome_unknown",
  "confirm_sender",
  "translate_email",
  "store_message",
  "pii_mask",
  "quarantine",
  "document_deleted",
  "private_mode",
  "disconnect_gmail",
] as const;
type NamedAction = (typeof NAMED_ACTIONS)[number];
const NAMED: ReadonlySet<string> = new Set(NAMED_ACTIONS);
const isNamed = (action: string): action is NamedAction => NAMED.has(action);

export function actionLabel(action: string, t: TFunction): string {
  return isNamed(action) ? t(`audit.actions.${action}`) : action;
}

/** The fields as they were recorded, key by key; nothing is parsed out of or added to them. */
export function fieldEntries(fields: AuditFields): [string, string][] {
  return Object.entries(fields).map(([key, value]) => [key, String(value)]);
}

/** Whether a record mentions the query in its action, fields, id or hash. */
export function matchesQuery(event: AuditTrailEvent, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (!needle) return true;
  const haystack = [event.action, event.id, event.currentHash ?? "", JSON.stringify(event.fields)];
  return haystack.some((text) => text.toLowerCase().includes(needle));
}
