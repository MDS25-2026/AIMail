import { placeholderPattern } from "./details";

// Mirrors backend/app/core/redaction.py REDACTION_MARKER: markers no vault can fill back in.
const REDACTION_MARKER = /\[(?:[A-Z_]+_REDACTED|Redacted|REDACTED)\]|\((?:hidden|name)\)/g;
// Any short bracketed text; the model sometimes writes "[Your Name]" or "[Company]" itself.
const BRACKETED = /\[[^[\]\n]{1,40}\]/g;

/** Markers still in a draft. Sent as-is, the recipient would read "[Redacted]" instead of a name. */
export function findRedactionMarkers(draft: string): string[] {
  return draft.match(REDACTION_MARKER) ?? [];
}

/**
 * Template text the model left for the reader to fill, such as "[Your Name]". Restorable
 * placeholders ([PERSON_1]) and redaction markers are not counted: the backend fills the first in
 * at send time and the marker warning covers the second.
 */
export function findTemplatePlaceholders(draft: string): string[] {
  return (draft.match(BRACKETED) ?? []).filter(
    (text) =>
      !new RegExp(`^${placeholderPattern().source}$`).test(text) && !text.match(REDACTION_MARKER),
  );
}

/** Whether replacing the draft would throw away text the reader typed. */
export function hasUnsavedEdits(typed: string | null, serverDraft: string): boolean {
  return typed !== null && typed !== serverDraft;
}
