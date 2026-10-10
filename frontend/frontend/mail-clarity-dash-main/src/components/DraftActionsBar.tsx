import { useTranslation } from "react-i18next";

import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import ApproveSendButton from "./ApproveSendButton";
import { button } from "./variants";

type DraftActionsBarProps = { workflow: DraftWorkflow; isSent: boolean };

export default function DraftActionsBar({ workflow, isSent }: DraftActionsBarProps) {
  // Every mutation blocks the others: the draft must not change under a send, and a send must
  // not go out mid-change. Sending is the irreversible one, so it is the one guarded hardest.
  const { t } = useTranslation();
  const isDraftChanging =
    workflow.isRegenerating ||
    workflow.isRefining ||
    workflow.isTemplating ||
    workflow.status.isGenerating;
  const isCountingDown = workflow.undoCountdown !== null && workflow.undoCountdown > 0;
  const blanks = workflow.unfilledBlanks;

  return (
    <div className="flex flex-col gap-2">
      {isCountingDown && (
        <div
          role="status"
          className="flex items-center justify-between rounded-md border border-warning-line bg-warning-soft px-3 py-2 text-sm text-warning"
        >
          <span>{t("draft.undoSendingIn", { count: workflow.undoCountdown })}</span>
          <button
            type="button"
            onClick={workflow.undoSend}
            className="ml-4 rounded border border-warning bg-surface px-3 py-1 text-xs font-semibold text-warning hover:bg-warning-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            {t("draft.undo")}
          </button>
        </div>
      )}
      {blanks.length > 0 ? (
        <p role="status" className="text-right text-xs text-warning">
          {t("templates.fillBlanks", { blanks: blanks.join(", "), count: blanks.length })}
        </p>
      ) : null}
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          disabled={workflow.isDraftLocked}
          onClick={workflow.regenerate}
          className={button({ size: "md" })}
        >
          {workflow.isRegenerating ? t("draft.regenerating") : t("draft.regenerate")}
        </button>
        <ApproveSendButton
          onApproveSend={workflow.send}
          isSending={workflow.isSending}
          isSent={isSent}
          isDraftChanging={isDraftChanging || isCountingDown}
          isBlocked={blanks.length > 0}
        />
      </div>
    </div>
  );
}
