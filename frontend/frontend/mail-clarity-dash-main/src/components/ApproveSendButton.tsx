import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
  const disabled = emailId === null || isSending || isSent || isDraftChanging;
  const label = isSent ? t("draft.sent") : isSending ? t("draft.sending") : t("draft.approveSend");
  const className = isSent
    ? "rounded-md bg-success px-4 py-2 text-sm font-semibold text-surface disabled:cursor-default"
    : "rounded-md bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-fg-subtle";

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={() => emailId && onApproveSend(emailId)}
      className={className}
    >
      {label}
    </button>
  );
}
