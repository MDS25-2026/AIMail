import type { ComposeDraft, ComposeList, ComposeSummary } from "../types/compose";

// backend/app/compose.py PREVIEW_CHARS, so a row changed here reads as the next fetch would.
const PREVIEW_CHARS = 140;

export const EMPTY_COMPOSE_LIST: ComposeList = { drafts: [], sent: [] };

/** The list row a saved draft has, built from the draft so autosave needs no list refetch. */
export function summaryOf(draft: ComposeDraft): ComposeSummary {
  const preview = (draft.body || draft.brief).split(/\s+/).filter(Boolean).join(" ");
  return {
    id: draft.id,
    to: draft.to,
    subject: draft.subject,
    preview: preview.slice(0, PREVIEW_CHARS),
    state: draft.state,
    updatedAt: draft.updatedAt,
    sentAt: draft.sentAt,
    details: draft.details,
  };
}

const newest = (at: (row: ComposeSummary) => string) => (a: ComposeSummary, b: ComposeSummary) =>
  at(b).localeCompare(at(a));

/** The list without this draft. */
export function withoutDraft(list: ComposeList, id: string): ComposeList {
  return {
    drafts: list.drafts.filter((row) => row.id !== id),
    sent: list.sent.filter((row) => row.id !== id),
  };
}

/** The list with this draft's row in its section, each section newest first. */
export function withDraft(list: ComposeList, draft: ComposeDraft): ComposeList {
  const rest = withoutDraft(list, draft.id);
  const row = summaryOf(draft);
  if (draft.sentAt) {
    return { ...rest, sent: [row, ...rest.sent].sort(newest((r) => r.sentAt ?? r.updatedAt)) };
  }
  return { ...rest, drafts: [row, ...rest.drafts].sort(newest((r) => r.updatedAt)) };
}
