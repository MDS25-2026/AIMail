import { diffWordsWithSpace } from "diff";

export type DiffKind = "same" | "added" | "removed";

export type DiffSegment = { text: string; kind: DiffKind };

/**
 * Word by word, what changed from `before` to `after` (#149). Spaces are kept as their own tokens,
 * so each side reads back exactly.
 */
export function diffDraft(before: string, after: string): DiffSegment[] {
  return diffWordsWithSpace(before, after).map((change) => ({
    text: change.value,
    kind: change.added ? "added" : change.removed ? "removed" : "same",
  }));
}

/** True when the diff has nothing to mark. */
export function isUnchanged(segments: DiffSegment[]): boolean {
  return segments.every((segment) => segment.kind === "same");
}
