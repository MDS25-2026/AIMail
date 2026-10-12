import { ChevronLeft, MoreHorizontal } from "lucide-react";
import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useSnoozeChoices, type SnoozeChoice } from "../lib/useSnoozeChoices";
import { cn } from "../lib/utils";
import { button } from "./variants";

export type MenuItem = { label: string; onSelect: () => void } | { label: string; href: string };

type RowMenuProps = {
  items: MenuItem[];
  onRemind?: (choice: SnoozeChoice) => void;
};

const ITEM =
  "flex min-h-11 w-full items-center rounded px-3 text-left text-sm text-fg hover:bg-surface-muted md:min-h-9";

/** A row's secondary actions: a dropdown on a desktop, a sheet along the bottom on a phone. */
export default function RowMenu({ items, onRemind }: RowMenuProps) {
  const { t } = useTranslation();
  const panelId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [isChoosingTime, setIsChoosingTime] = useState(false);
  const choices = useSnoozeChoices();
  const close = () => {
    setIsOpen(false);
    setIsChoosingTime(false);
  };

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setIsOpen(false);
      setIsChoosingTime(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen]);

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={t("todo.moreActions")}
        title={t("todo.moreActions")}
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={() => (isOpen ? close() : setIsOpen(true))}
        className={cn(
          button({ intent: "quiet", size: "xs" }),
          "min-w-11 px-0 md:size-8 md:min-w-0",
        )}
      >
        <MoreHorizontal aria-hidden className="size-4" />
      </button>
      {isOpen ? (
        <>
          {/* Closes on a tap outside; dims the page on a phone only. Above the z-50 chat button. */}
          <button
            type="button"
            tabIndex={-1}
            aria-label={t("todo.close")}
            onClick={close}
            className="fixed inset-0 z-[60] cursor-default bg-rail/60 md:bg-transparent"
          />
          <div
            id={panelId}
            className="fixed inset-x-0 bottom-0 z-[70] space-y-1 rounded-t-xl border border-line bg-surface p-3 pb-6 shadow-lg md:absolute md:inset-auto md:right-0 md:top-full md:mt-1 md:w-60 md:rounded-md md:p-1.5 md:pb-1.5"
          >
            {isChoosingTime ? (
              <>
                <button
                  type="button"
                  onClick={() => setIsChoosingTime(false)}
                  className={cn(ITEM, "gap-1 text-fg-muted")}
                >
                  <ChevronLeft aria-hidden className="size-4" />
                  {t("todo.remindLater")}
                </button>
                {choices.map((choice) => (
                  <button
                    key={choice.label}
                    type="button"
                    onClick={() => {
                      close();
                      onRemind?.(choice);
                    }}
                    className={ITEM}
                  >
                    {choice.label}
                  </button>
                ))}
              </>
            ) : (
              <>
                {onRemind ? (
                  <button type="button" onClick={() => setIsChoosingTime(true)} className={ITEM}>
                    {t("todo.remindLater")}
                  </button>
                ) : null}
                {items.map((item) =>
                  "href" in item ? (
                    <a
                      key={item.label}
                      href={item.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={close}
                      className={ITEM}
                    >
                      {item.label}
                    </a>
                  ) : (
                    <button
                      key={item.label}
                      type="button"
                      onClick={() => {
                        close();
                        item.onSelect();
                      }}
                      className={ITEM}
                    >
                      {item.label}
                    </button>
                  ),
                )}
              </>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
