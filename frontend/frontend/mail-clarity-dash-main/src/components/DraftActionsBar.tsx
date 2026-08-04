import ApproveSendButton from "./ApproveSendButton";

type DraftActionsBarProps = {
  emailId: string | null;
  onRegenerate: (emailId: string) => void;
  onApproveSend: (emailId: string) => void;
  isRegenerating?: boolean;
};

export default function DraftActionsBar({
  emailId,
  onRegenerate,
  onApproveSend,
  isRegenerating = false,
}: DraftActionsBarProps) {
  return (
    <div className="flex items-center justify-end gap-2">
      <button
        type="button"
        disabled={emailId === null || isRegenerating}
        onClick={() => emailId && onRegenerate(emailId)}
        className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
      >
        {isRegenerating ? "Regenerating…" : "Regenerate"}
      </button>
      <ApproveSendButton emailId={emailId} onApproveSend={onApproveSend} />
    </div>
  );
}
