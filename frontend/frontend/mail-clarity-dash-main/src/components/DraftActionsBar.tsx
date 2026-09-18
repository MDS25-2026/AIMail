import ApproveSendButton from "./ApproveSendButton";

type DraftActionsBarProps = {
  emailId: string | null;
  onRegenerate: (emailId: string) => void;
  onApproveSend: (emailId: string) => void;
  isRegenerating?: boolean;
  isRefining?: boolean;
  isSending?: boolean;
  isSent?: boolean;
};

export default function DraftActionsBar({
  emailId,
  onRegenerate,
  onApproveSend,
  isRegenerating = false,
  isRefining = false,
  isSending = false,
  isSent = false,
}: DraftActionsBarProps) {
  // Every mutation blocks the others: the draft must not change under a send, and a send must
  // not go out mid-change. Sending is the irreversible one, so it is the one guarded hardest.
  const isDraftChanging = isRegenerating || isRefining;
  return (
    <div className="flex items-center justify-end gap-2">
      <button
        type="button"
        disabled={emailId === null || isRegenerating || isRefining || isSending}
        onClick={() => emailId && onRegenerate(emailId)}
        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
      >
        {isRegenerating ? "Regenerating…" : "Regenerate"}
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
