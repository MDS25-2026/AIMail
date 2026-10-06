type ApproveSendButtonProps = {
  emailId: string | null;
  onApproveSend: (emailId: string) => void;
  isSending?: boolean;
  isSent?: boolean;
  /** A draft mutation is in flight. Sending now would dispatch the pre-mutation text while the
   *  screen goes on to show the new one — and a send cannot be taken back. */
  isDraftChanging?: boolean;
};

/**
 * The ONLY path that sends a reply. Deliberately the single solid-navy action
 * so it is never confused with Regenerate / Refine. Turns green + disabled once sent.
 */
export default function ApproveSendButton({
  emailId,
  onApproveSend,
  isSending = false,
  isSent = false,
  isDraftChanging = false,
}: ApproveSendButtonProps) {
  const disabled = emailId === null || isSending || isSent || isDraftChanging;
  const label = isSent ? "Sent" : isSending ? "Sending…" : "Approve & Send";
  const className = isSent
    ? "rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-default"
    : "rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300";

  return (
    <button type="button" disabled={disabled} onClick={() => emailId && onApproveSend(emailId)} className={className}>
      {label}
    </button>
  );
}
