type ApproveSendButtonProps = {
  emailId: string | null;
  onApproveSend: (emailId: string) => void;
};

/**
 * The ONLY path that sends a reply. Deliberately the single near-black action
 * so it is never confused with Regenerate / Refine.
 */
export default function ApproveSendButton({ emailId, onApproveSend }: ApproveSendButtonProps) {
  const disabled = emailId === null;

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => emailId && onApproveSend(emailId)}
      className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
    >
      Approve &amp; Send
    </button>
  );
}
