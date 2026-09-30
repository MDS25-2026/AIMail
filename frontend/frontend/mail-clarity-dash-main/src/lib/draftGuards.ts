// Mirrors email_agent._PLACEHOLDER: the listener's regex tokens, Presidio's replacement and the OCR transcription.
const REDACTION_MARKER = /\[(?:[A-Z_]+_REDACTED|Redacted|REDACTED)\]/g;

/** Markers still in a draft. Sent as-is, the recipient would read "[Redacted]" instead of a name. */
export function findRedactionMarkers(draft: string): string[] {
  return draft.match(REDACTION_MARKER) ?? [];
}

/** Whether replacing the draft would throw away text the reader typed. */
export function hasUnsavedEdits(typed: string | null, serverDraft: string): boolean {
  return typed !== null && typed !== serverDraft;
}
