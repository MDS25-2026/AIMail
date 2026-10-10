import { CircleAlert, LoaderCircle, TriangleAlert } from "lucide-react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import type { QuietSuggestion } from "../lib/quietHours";
import { useFormat } from "../lib/useFormat";
import { ConfirmKind, DraftAction, type DraftWorkflowStatus } from "../lib/useDraftWorkflow";

type DraftStatusProps = DraftWorkflowStatus;

function quietMessage(quiet: QuietSuggestion, t: TFunction, clock: Clock): string {
  const whose = quiet.isTheirTime ? "them" : "you";
  return t(`draftStatus.quietHours.${whose}`, {
    now: clock(quiet.theirNow, quiet.offsetMinutes),
    sendAt: clock(quiet.sendAt, quiet.offsetMinutes),
  });
}

type Clock = (at: Date, offsetMinutes: number) => string;

function confirmMessage(kind: ConfirmKind, count: number, t: TFunction): string {
  if (kind === ConfirmKind.ReplaceEdits) return t("draftStatus.replaceEdits");
  if (kind === ConfirmKind.SendTemplates) return t("draftStatus.sendTemplates", { count });
  if (kind === ConfirmKind.ToneWarning) return t("draftStatus.toneWarning");
  return t("draftStatus.sendMarkers", { count });
}

// What to say when the backend names no reason: each action leaves the draft as it was.
const FALLBACK_BY_ACTION = {
  [DraftAction.Regenerate]: "draftStatus.failed.regenerate",
  [DraftAction.Refine]: "draftStatus.failed.refine",
  [DraftAction.Template]: "draftStatus.failed.template",
  [DraftAction.Schedule]: "draftStatus.failed.schedule",
  [DraftAction.CancelSchedule]: "draftStatus.failed.cancelSchedule",
  [DraftAction.Send]: "draftStatus.failed.send",
} as const;

const BUTTON =
  "rounded-md border px-3 py-1.5 text-xs font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

/** Everything the reader must know before acting on the draft, directly above the actions. */
export default function DraftStatus({
  failure,
  pendingConfirm,
  onConfirm,
  onCancel,
  onSendAtSuggestion,
  isGenerating,
  isLoadFailed,
  onRetryLoad,
}: DraftStatusProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const quiet = pendingConfirm?.quiet;

  const confirmLabel =
    pendingConfirm?.kind === ConfirmKind.ReplaceEdits
      ? t("draftStatus.replaceConfirm")
      : t("draftStatus.sendAnyway");

  return (
    <div className="space-y-2 empty:hidden">
      {pendingConfirm ? (
        <div
          role="alert"
          className="flex flex-wrap items-start gap-3 rounded-md border border-warning-line bg-warning-soft p-3"
        >
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
          <p className="min-w-0 flex-1 text-sm text-warning">
            {quiet
              ? quietMessage(quiet, t, format.clock)
              : confirmMessage(pendingConfirm.kind, pendingConfirm.markerCount, t)}
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
            {quiet ? (
              <button
                type="button"
                onClick={onSendAtSuggestion}
                className={`${BUTTON} border-warning bg-surface text-warning`}
              >
                {t("draftStatus.quietHours.sendLater", {
                  time: format.clock(quiet.sendAt, quiet.offsetMinutes),
                })}
              </button>
            ) : null}
            <button
              type="button"
              onClick={onConfirm}
              className={`${BUTTON} border-warning bg-warning text-surface`}
            >
              {quiet ? t("draftStatus.quietHours.sendNow") : confirmLabel}
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
          {errorMessage(failure.error, t, FALLBACK_BY_ACTION[failure.action])}
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
