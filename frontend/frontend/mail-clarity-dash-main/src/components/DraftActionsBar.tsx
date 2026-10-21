import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import { cn } from "../lib/utils";
import ApproveSendButton from "./ApproveSendButton";
import RemindCheckbox from "./RemindCheckbox";
import SendLaterMenu from "./SendLaterMenu";
import UndoSendBar from "./UndoSendBar";
import { button } from "./variants";

type DraftActionsBarProps = {
  workflow: DraftWorkflow;
  isSent: boolean;
  /** Where the reply goes when that is not the sender (a Reply-To header), or null. */
  replyElsewhere?: string | null;
};

export default function DraftActionsBar({
  workflow,
  isSent,
  replyElsewhere = null,
}: DraftActionsBarProps) {
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
      <UndoSendBar secondsLeft={workflow.undoCountdown} onUndo={workflow.undoSend} />
      {isSent ? null : (
        <RemindCheckbox
          isChecked={workflow.remindIfNoReply}
          disabled={workflow.isDraftLocked}
          onChange={workflow.setRemindIfNoReply}
        />
      )}
      {replyElsewhere && !isSent ? (
        // A forged Reply-To is how a reply gets diverted; the approver must see it before sending.
        <p role="note" className="text-right text-xs text-warning">
          {t("draft.replyGoesTo", { address: replyElsewhere })}
        </p>
      ) : null}
      {blanks.length > 0 ? (
        <p role="status" className="text-right text-xs text-warning">
          {t("templates.fillBlanks", { blanks: blanks.join(", "), count: blanks.length })}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          disabled={workflow.isDraftLocked}
          onClick={workflow.regenerate}
          className={cn(button({ size: "md" }), "min-w-11 gap-1.5 whitespace-nowrap")}
        >
          <RefreshCw aria-hidden className="size-4" />
          {/* Icon only on a phone, so the three actions fit one row; the name stays for screen readers. */}
          <span className="sr-only md:not-sr-only">
            {workflow.isRegenerating ? t("draft.regenerating") : t("draft.regenerate")}
          </span>
        </button>
        <SendLaterMenu workflow={workflow} isBlocked={blanks.length > 0} />
        <ApproveSendButton
          onApproveSend={workflow.send}
          isSending={workflow.isSending}
          isSent={isSent}
          isDraftChanging={isDraftChanging || isCountingDown}
          isBlocked={blanks.length > 0 || workflow.isDraftLocked}
        />
      </div>
    </div>
  );
}
