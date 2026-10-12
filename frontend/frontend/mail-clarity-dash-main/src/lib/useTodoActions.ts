import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "./api/errors";
import {
  useDismissEmail,
  useNotWaiting,
  useRemindLater,
  useUndismissEmail,
  useWaitingAgain,
  useWakeEmail,
} from "./queries";
import { useFormat } from "./useFormat";
import type { SnoozeChoice } from "./useSnoozeChoices";

export type Undoable = { id: number; label: string; undo: () => Promise<unknown> };

export type TodoActions = ReturnType<typeof useTodoActions>;

/** The To-do's removals and their undo. Kept in the page: a removed row unmounts at once, and the
 *  notice must still appear when the server answers. */
export function useTodoActions() {
  const { t } = useTranslation();
  const format = useFormat();
  const dismissEmail = useDismissEmail();
  const remindLater = useRemindLater();
  const notWaitingOn = useNotWaiting();
  const undismiss = useUndismissEmail();
  const wake = useWakeEmail();
  const waitingAgain = useWaitingAgain();
  const [notice, setNotice] = useState<Undoable | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nextId = useRef(0);

  const offerUndo = (label: string, undo: () => Promise<unknown>) => {
    nextId.current += 1;
    setError(null);
    setNotice({ id: nextId.current, label, undo });
  };
  const fail = (failure: Error) => setError(errorMessage(failure, t, "todo.failed"));

  const dismiss = (emailId: string) =>
    dismissEmail.mutate(emailId, {
      onSuccess: () => offerUndo(t("todo.undone.dismissed"), () => undismiss.mutateAsync(emailId)),
      onError: fail,
    });
  const remind = (emailId: string, choice: SnoozeChoice) =>
    remindLater.mutate(
      { emailId, until: choice.at },
      {
        onSuccess: () =>
          offerUndo(
            t("todo.undone.reminded", { when: format.timestamp(choice.at.toISOString()) }),
            () => wake.mutateAsync({ emailId }),
          ),
        onError: fail,
      },
    );
  const notWaiting = (sentId: string) =>
    notWaitingOn.mutate(sentId, {
      onSuccess: () =>
        offerUndo(t("todo.undone.notWaiting"), () => waitingAgain.mutateAsync(sentId)),
      onError: fail,
    });
  const clear = useCallback(() => {
    setNotice(null);
    setError(null);
  }, []);

  return { dismiss, remind, notWaiting, notice, error, clear, failUndo: setError };
}
