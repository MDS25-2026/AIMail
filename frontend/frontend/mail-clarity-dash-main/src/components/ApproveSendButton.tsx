import { useTranslation } from "react-i18next";

import { cn } from "../lib/utils";
import { button } from "./variants";

type ApproveSendButtonProps = {
  onApproveSend: () => void;
  isSending: boolean;
  isSent: boolean;
  /** A draft mutation is in flight. Sending now would dispatch the pre-mutation text while the
   *  screen goes on to show the new one — and a send cannot be taken back. */
  isDraftChanging: boolean;
  /** The draft still holds a saved template's {{blank}}; the backend would refuse it. */
  isBlocked?: boolean;
};

const SENT =
  "rounded-md bg-success px-4 py-2 text-sm font-semibold text-surface disabled:cursor-default";

/**
 * The ONLY path that sends a reply. Deliberately the single solid-navy action
 * so it is never confused with Regenerate / Refine. Turns green + disabled once sent.
 */
export default function ApproveSendButton({
  onApproveSend,
  isSending,
  isSent,
  isDraftChanging,
  isBlocked = false,
}: ApproveSendButtonProps) {
  const { t } = useTranslation();
  const disabled = isSending || isSent || isDraftChanging || isBlocked;
  const label = isSent ? t("draft.sent") : isSending ? t("draft.sending") : t("draft.approveSend");
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onApproveSend}
      className={isSent ? SENT : cn(button({ intent: "primary", size: "md" }), "whitespace-nowrap")}
    >
      {label}
    </button>
  );
}
