import { isPlaceholder, redactionMarkerPattern } from "./masking";

// Any short bracketed text; the model sometimes writes "[Your Name]" or "[Company]" itself.
const BRACKETED = /\[[^[\]\n]{1,40}\]/g;

/** Markers still in a draft. Sent as-is, the recipient would read "[Redacted]" instead of a name. */
export function findRedactionMarkers(draft: string): string[] {
  return draft.match(redactionMarkerPattern()) ?? [];
}

/**
 * Template text the model left for the reader to fill, such as "[Your Name]". Restorable
 * placeholders ([PERSON_1]) and redaction markers are not counted: the backend fills the first in
 * at send time and the marker warning covers the second.
 */
export function findTemplatePlaceholders(draft: string): string[] {
  return (draft.match(BRACKETED) ?? []).filter(
    (text) => !isPlaceholder(text) && !redactionMarkerPattern().test(text),
  );
}

/** Whether replacing the draft would throw away text the reader typed. */
export function hasUnsavedEdits(typed: string | null, serverDraft: string): boolean {
  return typed !== null && typed !== serverDraft;
}
