import type { DetailValues } from "./details";
import { kindOf, placeholderPattern, redactionMarkerPattern, type HiddenKind } from "./masking";

/**
 * Privacy receipt and hidden-detail chips (#158). Pure helpers: which details the AI never saw,
 * and which of them the reader still has to fill in before sending.
 */

/** Each hidden detail in the draft that will not be filled in at send, in reading order. */
export function unfilledMarkers(draft: string, values: DetailValues): string[] {
  const placeholders = [...draft.matchAll(placeholderPattern())]
    .filter((match) => !values.has(match[0]))
    .map((match) => ({ text: match[0], at: match.index ?? 0 }));
  const markers = [...draft.matchAll(redactionMarkerPattern())].map((match) => ({
    text: match[0],
    at: match.index ?? 0,
  }));
  return [...placeholders, ...markers].sort((a, b) => a.at - b.at).map((found) => found.text);
}

/** The draft with the first occurrence of `marker` replaced by what the reader typed. */
export function fillFirst(draft: string, marker: string, value: string): string {
  const at = draft.indexOf(marker);
  if (at < 0 || !value.trim()) return draft;
  return draft.slice(0, at) + value.trim() + draft.slice(at + marker.length);
}

export type KindCount = { kind: HiddenKind; count: number };

/** How many details of each kind were hidden from the AI in this text, most first. */
export function hiddenCounts(text: string): KindCount[] {
  // One person named three times is one hidden name; each marker stands alone.
  const placeholders = new Set([...text.matchAll(placeholderPattern())].map((match) => match[0]));
  const markers = [...text.matchAll(redactionMarkerPattern())].map((match) => match[0]);
  const found = [...placeholders, ...markers].map(kindOf);
  const counts = new Map<HiddenKind, number>();
  for (const kind of found) counts.set(kind, (counts.get(kind) ?? 0) + 1);
  return [...counts].map(([kind, count]) => ({ kind, count })).sort((a, b) => b.count - a.count);
}
