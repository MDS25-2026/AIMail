import { useTranslation } from "react-i18next";

import { useQuietHours } from "./queries";
import { nextHourHere, nextMondayHere, nextQuietEnd, zoneOffsetMinutes } from "./quietHours";

const LATER_TODAY_HOURS = 3;
const MORNING_HOUR = 9;
const MS_PER_HOUR = 3_600_000;

export type SnoozeChoice = { label: string; at: Date };

/** The times an email can be put off until: the email's Snooze and the To-do's Remind me later. */
export function useSnoozeChoices(): SnoozeChoice[] {
  const { t } = useTranslation();
  const quietHours = useQuietHours();
  const now = new Date();
  const hours = quietHours.data?.effective;
  const quietEnd = hours ? nextQuietEnd(now, zoneOffsetMinutes(hours.timezone, now), hours) : null;
  return [
    {
      label: t("snooze.laterToday"),
      at: new Date(now.getTime() + LATER_TODAY_HOURS * MS_PER_HOUR),
    },
    { label: t("snooze.tomorrow"), at: nextHourHere(now, MORNING_HOUR, 1) },
    { label: t("snooze.nextWeek"), at: nextMondayHere(now, MORNING_HOUR) },
    ...(quietEnd ? [{ label: t("snooze.quietEnd"), at: quietEnd }] : []),
  ];
}
