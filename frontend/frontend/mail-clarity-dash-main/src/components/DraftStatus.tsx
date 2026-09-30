import { CircleAlert, LoaderCircle, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ConfirmKind, type DraftWorkflowStatus } from "../lib/useDraftWorkflow";

export type DraftStatusProps = DraftWorkflowStatus & {
  isGenerating: boolean;
  isLoadFailed: boolean;
  onRetryLoad: () => void;
};

const BUTTON =
  "rounded-md border px-3 py-1.5 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

/** Everything the reader must know before acting on the draft, directly above the actions. */
export default function DraftStatus({
  failure,
  pendingConfirm,
  onConfirm,
  onCancel,
  isGenerating,
  isLoadFailed,
  onRetryLoad,
}: DraftStatusProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-2 empty:hidden">
      {pendingConfirm ? (
        <div
          role="alert"
          className="flex flex-wrap items-start gap-3 rounded-md border border-warning-line bg-warning-soft p-3"
        >
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
          <p className="min-w-0 flex-1 text-sm text-warning">
            {pendingConfirm.kind === ConfirmKind.ReplaceEdits
              ? t("draftStatus.replaceEdits")
              : t("draftStatus.sendMarkers", { count: pendingConfirm.markerCount })}
          </p>
          <div className="flex gap-2">
            {/* The safe choice takes focus, so Enter never confirms by accident. */}
            <button
              type="button"
              autoFocus
              onClick={onCancel}
              className={`${BUTTON} border-line-strong bg-surface text-fg-body`}
            >
              {t("draftStatus.keepEditing")}
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className={`${BUTTON} border-warning bg-warning text-surface`}
            >
              {pendingConfirm.kind === ConfirmKind.ReplaceEdits
                ? t("draftStatus.replaceConfirm")
                : t("draftStatus.sendAnyway")}
            </button>
          </div>
        </div>
      ) : null}

      {failure ? (
        <p
          role="alert"
          className="flex gap-2 rounded-md border border-danger-line bg-danger-soft p-3 text-sm text-danger"
        >
          <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          {t(`draftStatus.failed.${failure}`)}
        </p>
      ) : null}

      {isGenerating ? (
        <p role="status" className="flex items-center gap-2 text-sm text-fg-muted">
          <LoaderCircle
            aria-hidden
            className="size-4 shrink-0 animate-spin motion-reduce:animate-none"
          />
          {t("draftStatus.generating")}
        </p>
      ) : null}

      {isLoadFailed ? (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-md border border-danger-line bg-danger-soft p-3"
        >
          <p className="min-w-0 flex-1 text-sm text-danger">{t("draftStatus.loadFailed")}</p>
          <button
            type="button"
            onClick={onRetryLoad}
            className={`${BUTTON} border-danger-line bg-surface text-danger`}
          >
            {t("draftStatus.retry")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
