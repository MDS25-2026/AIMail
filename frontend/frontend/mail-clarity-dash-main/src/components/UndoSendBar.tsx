import { useTranslation } from "react-i18next";

type UndoSendBarProps = { secondsLeft: number | null; onUndo: () => void };

/** "Sending in 5 seconds… Undo", for a reply or a new email in its undo window. */
export default function UndoSendBar({ secondsLeft, onUndo }: UndoSendBarProps) {
  const { t } = useTranslation();
  if (secondsLeft === null || secondsLeft <= 0) return null;
  return (
    <div
      role="status"
      className="flex items-center justify-between rounded-md border border-warning-line bg-warning-soft px-3 py-2 text-sm text-warning"
    >
      <span>{t("draft.undoSendingIn", { count: secondsLeft })}</span>
      <button
        type="button"
        onClick={onUndo}
        className="ml-4 rounded border border-warning bg-surface px-3 py-1 text-xs font-semibold text-warning hover:bg-warning-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        {t("draft.undo")}
      </button>
    </div>
  );
}
