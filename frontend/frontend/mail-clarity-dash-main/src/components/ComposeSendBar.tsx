import { CircleAlert, LoaderCircle } from "lucide-react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { findUnfilledBlanks } from "../lib/draftGuards";
import { ComposeAction, type ComposeWorkflow } from "../lib/useComposeDraft";
import ApproveSendButton from "./ApproveSendButton";
import RemindCheckbox from "./RemindCheckbox";
import UndoSendBar from "./UndoSendBar";

/** Approve & Send with the reply's undo window, and why it is not possible yet, in words. */
export default function ComposeSendBar({ compose }: { compose: ComposeWorkflow }) {
  const { t } = useTranslation();
  const blocker = compose.blockers[0];
  const reasonId = useId();
  const isCountingDown = compose.undoCountdown !== null;
  const isChanging =
    compose.busy === ComposeAction.Write || compose.busy === ComposeAction.Refine || isCountingDown;
  const blanks = findUnfilledBlanks(compose.fields.body).join(", ");
  return (
    <div className="flex flex-col gap-2 border-t border-line-subtle pt-4">
      <UndoSendBar secondsLeft={compose.undoCountdown} onUndo={compose.undoSend} />
      <RemindCheckbox
        isChecked={compose.remindIfNoReply}
        disabled={compose.isLocked}
        onChange={compose.setRemindIfNoReply}
      />
      {blocker ? (
        <p
          id={reasonId}
          className="flex items-start justify-end gap-1.5 text-right text-xs text-fg-muted"
        >
          <CircleAlert aria-hidden className="mt-0.5 size-3.5 shrink-0" />
          {t(`compose.blocked.${blocker}`, { blanks })}
        </p>
      ) : null}
      {compose.isSending ? (
        <p role="status" className="flex items-center justify-end gap-2 text-sm text-fg-muted">
          <LoaderCircle
            aria-hidden
            className="size-4 shrink-0 animate-spin motion-reduce:animate-none"
          />
          {t("compose.sendingLocked")}
        </p>
      ) : null}
      <div className="flex justify-end">
        <ApproveSendButton
          onApproveSend={compose.send}
          isSending={compose.isSending}
          isSent={false}
          isDraftChanging={isChanging}
          isBlocked={compose.blockers.length > 0 || compose.isLocked}
          describedBy={blocker ? reasonId : undefined}
        />
      </div>
    </div>
  );
}
