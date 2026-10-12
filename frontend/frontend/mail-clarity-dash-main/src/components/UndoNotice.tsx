import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import type { Undoable } from "../lib/useTodoActions";

/** Long enough to notice and reach the button; the usual window for undo over a confirm prompt. */
export const UNDO_MS = 8_000;

type UndoNoticeProps = {
  action: Undoable | null;
  error: string | null;
  onDone: () => void;
  onFailed: (message: string) => void;
};

/** "{what} · Undo" along the bottom for UNDO_MS; a newer action replaces it. */
export default function UndoNotice({ action, error, onDone, onFailed }: UndoNoticeProps) {
  const { t } = useTranslation();
  useEffect(() => {
    if (!action && !error) return;
    const timer = window.setTimeout(onDone, UNDO_MS);
    return () => window.clearTimeout(timer);
  }, [action, error, onDone]);

  const message = error ?? action?.label;
  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-20 z-30 flex justify-center px-4 md:bottom-6"
    >
      {message ? (
        <div className="pointer-events-auto flex items-center gap-3 rounded-lg bg-fg px-4 py-2 text-sm text-surface shadow-lg">
          <span>{message}</span>
          {action && !error ? (
            <button
              type="button"
              onClick={() => {
                onDone();
                action.undo().catch(() => onFailed(t("todo.undoFailed")));
              }}
              className="min-h-11 rounded px-2 font-semibold text-surface underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-surface md:min-h-0 md:py-1"
            >
              {t("todo.undo")}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
