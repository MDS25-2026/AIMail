import { useTranslation } from "react-i18next";

import ApproveSendButton from "./ApproveSendButton";

type DraftActionsBarProps = {
  emailId: string | null;
  onRegenerate: (emailId: string) => void;
  onApproveSend: (emailId: string) => void;
  isRegenerating?: boolean;
  isRefining?: boolean;
  isSending?: boolean;
  isSent?: boolean;
  /** The first draft is still being written; acting now would act on the preview. */
  isGenerating?: boolean;
};

export default function DraftActionsBar({
  emailId,
  onRegenerate,
  onApproveSend,
  isRegenerating = false,
  isRefining = false,
  isSending = false,
  isSent = false,
  isGenerating = false,
}: DraftActionsBarProps) {
  // Every mutation blocks the others: the draft must not change under a send, and a send must
  // not go out mid-change. Sending is the irreversible one, so it is the one guarded hardest.
  const { t } = useTranslation();
  const isDraftChanging = isRegenerating || isRefining || isGenerating;
  return (
    <div className="flex items-center justify-end gap-2">
      <button
        type="button"
        disabled={emailId === null || isDraftChanging || isSending}
        onClick={() => emailId && onRegenerate(emailId)}
        className="rounded-md border border-line-strong bg-surface px-4 py-2 text-sm font-medium text-fg-body hover:bg-surface-muted disabled:cursor-not-allowed disabled:text-fg-subtle"
      >
        {isRegenerating ? t("draft.regenerating") : t("draft.regenerate")}
      </button>
      <ApproveSendButton
        emailId={emailId}
        onApproveSend={onApproveSend}
        isSending={isSending}
        isSent={isSent}
        isDraftChanging={isDraftChanging}
      />
    </div>
  );
}
