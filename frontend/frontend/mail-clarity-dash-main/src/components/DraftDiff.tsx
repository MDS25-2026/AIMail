import { useTranslation } from "react-i18next";

import { diffDraft, isUnchanged } from "../lib/draftDiff";
import type { DraftComparison } from "../lib/useDraftWorkflow";

type DraftDiffProps = { comparison: DraftComparison; rows: number };

const ADDED = "rounded-sm bg-success-soft text-success underline decoration-success";
const REMOVED = "rounded-sm bg-danger-soft text-danger line-through decoration-danger";

/** Read-only, word-level view of what changed in the draft (#149). */
export default function DraftDiff({ comparison, rows }: DraftDiffProps) {
  const { t } = useTranslation();
  const segments = diffDraft(comparison.before, comparison.after);
  const unchanged = isUnchanged(segments);
  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <p className="font-medium text-fg-muted">{t(`draftDiff.source.${comparison.source}`)}</p>
        {unchanged ? null : (
          <p aria-hidden className="flex items-center gap-2">
            <span className={`px-1 ${ADDED}`}>{t("draftDiff.added")}</span>
            <span className={`px-1 ${REMOVED}`}>{t("draftDiff.removed")}</span>
          </p>
        )}
      </div>
      {/* Sized like the text box it replaces, so toggling doesn't move the controls below. */}
      <div
        className="relative mt-1.5 w-full overflow-y-auto whitespace-pre-wrap break-words rounded-md border border-line-strong bg-surface-muted p-3 text-sm leading-relaxed text-fg"
        style={{ minHeight: `${rows * 1.5 + 1.5}rem` }}
      >
        {unchanged ? (
          <p className="text-fg-subtle">{t(`draftDiff.none.${comparison.source}`)}</p>
        ) : (
          segments.map((segment, index) => {
            if (segment.kind === "added") {
              return (
                <ins key={index} className={ADDED}>
                  <span className="sr-only">{t("draftDiff.addedLabel")}</span>
                  {segment.text}
                </ins>
              );
            }
            if (segment.kind === "removed") {
              return (
                <del key={index} className={REMOVED}>
                  <span className="sr-only">{t("draftDiff.removedLabel")}</span>
                  {segment.text}
                </del>
              );
            }
            return <span key={index}>{segment.text}</span>;
          })
        )}
      </div>
    </div>
  );
}
