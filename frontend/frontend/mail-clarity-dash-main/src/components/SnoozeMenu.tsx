import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { useQuietHours, useSnoozeEmail, useUnsnoozeEmail } from "../lib/queries";
import { nextHourHere, nextMondayHere, nextQuietEnd, zoneOffsetMinutes } from "../lib/quietHours";
import { useFormat } from "../lib/useFormat";
import type { Email } from "../types/email";
import { InlineAlert } from "./InlineMessages";
import { button } from "./variants";

const LATER_TODAY_HOURS = 3;
const MORNING_HOUR = 9;
const MS_PER_HOUR = 3_600_000;

/** Snooze (specs/features/quiet-hours-send-later.md): out of the inbox, back unread when due. */
export default function SnoozeMenu({ email }: { email: Email }) {
  const { t } = useTranslation();
  const format = useFormat();
  const panelId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const snooze = useSnoozeEmail();
  const unsnooze = useUnsnoozeEmail();
  const quietHours = useQuietHours();
  const error = snooze.error ?? unsnooze.error;
  const isSnoozed =
    email.snoozedUntil !== null &&
    email.snoozedUntil !== undefined &&
    new Date(email.snoozedUntil) > new Date();

  if (isSnoozed && email.snoozedUntil) {
    return (
      <span className="flex items-center gap-2 text-xs text-fg-muted">
        {t("snooze.until", { when: format.timestamp(email.snoozedUntil) })}
        <button
          type="button"
          disabled={unsnooze.isPending}
          onClick={() => unsnooze.mutate({ emailId: email.id })}
          className={button({ size: "xs" })}
        >
          {t("snooze.wake")}
        </button>
      </span>
    );
  }

  const now = new Date();
  const hours = quietHours.data?.effective;
  const quietEnd = hours ? nextQuietEnd(now, zoneOffsetMinutes(hours.timezone, now), hours) : null;
  const choices = [
    {
      label: t("snooze.laterToday"),
      at: new Date(now.getTime() + LATER_TODAY_HOURS * MS_PER_HOUR),
    },
    { label: t("snooze.tomorrow"), at: nextHourHere(now, MORNING_HOUR, 1) },
    { label: t("snooze.nextWeek"), at: nextMondayHere(now, MORNING_HOUR) },
    ...(quietEnd ? [{ label: t("snooze.quietEnd"), at: quietEnd }] : []),
  ];
  return (
    <div className="relative">
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={() => setIsOpen((open) => !open)}
        className={button({ size: "xs" })}
      >
        {snooze.isPending ? t("snooze.snoozing") : t("snooze.snooze")}
      </button>
      {isOpen ? (
        <div
          id={panelId}
          className="absolute right-0 top-full z-10 mt-1 w-52 space-y-1 rounded-md border border-line bg-surface p-2 shadow-md"
        >
          {choices.map((choice) => (
            <button
              key={choice.label}
              type="button"
              onClick={() => {
                setIsOpen(false);
                snooze.mutate({ emailId: email.id, until: choice.at });
              }}
              className={`${button({ size: "xs" })} w-full text-left`}
            >
              {choice.label}
            </button>
          ))}
        </div>
      ) : null}
      {error ? (
        <InlineAlert size="xs">{errorMessage(error, t, "snooze.failed")}</InlineAlert>
      ) : null}
    </div>
  );
}
