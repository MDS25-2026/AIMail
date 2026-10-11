import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { nextHourHere, nextMondayHere } from "../lib/quietHours";
import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import { cn } from "../lib/utils";
import { button, field } from "./variants";

// The morning a held reply goes out by default, on the reader's own clock.
const MORNING_HOUR = 9;

type SendLaterMenuProps = { workflow: DraftWorkflow; isBlocked: boolean };

/** Send later (specs/features/quiet-hours-send-later.md): the reply is held and sent when due. */
export default function SendLaterMenu({ workflow, isBlocked }: SendLaterMenuProps) {
  const { t } = useTranslation();
  const panelId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [custom, setCustom] = useState("");
  const isDisabled = workflow.isDraftLocked || isBlocked;
  const schedule = (at: Date) => {
    setIsOpen(false);
    workflow.schedule(at);
  };
  const now = new Date();
  const choices = [
    { label: t("schedule.tomorrow"), at: nextHourHere(now, MORNING_HOUR, 1) },
    { label: t("schedule.monday"), at: nextMondayHere(now, MORNING_HOUR) },
  ];

  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={panelId}
        disabled={isDisabled}
        onClick={() => setIsOpen((open) => !open)}
        className={cn(button({ size: "md" }), "whitespace-nowrap")}
      >
        {workflow.isScheduling ? t("schedule.scheduling") : t("schedule.sendLater")}
      </button>
      {isOpen ? (
        <div
          id={panelId}
          className="absolute bottom-full right-0 z-10 mb-2 w-64 space-y-2 rounded-md border border-line bg-surface p-3 shadow-md"
        >
          {choices.map((choice) => (
            <button
              key={choice.label}
              type="button"
              onClick={() => schedule(choice.at)}
              className={`${button({ size: "sm" })} w-full text-left`}
            >
              {choice.label}
            </button>
          ))}
          <label className="block space-y-1">
            <span className="text-xs font-medium text-fg-muted">{t("schedule.pickTime")}</span>
            <input
              type="datetime-local"
              value={custom}
              onChange={(event) => setCustom(event.target.value)}
              className={`${field({ size: "sm" })} w-full`}
            />
          </label>
          <button
            type="button"
            disabled={custom === ""}
            onClick={() => schedule(new Date(custom))}
            className={`${button({ intent: "primary", size: "sm" })} w-full`}
          >
            {t("schedule.scheduleAt")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
