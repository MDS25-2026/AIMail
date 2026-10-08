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
    workflow.isRegenerating || workflow.isRefining || workflow.status.isGenerating;
  return (
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
        isDraftChanging={isDraftChanging}
      />
    </div>
  );
}
