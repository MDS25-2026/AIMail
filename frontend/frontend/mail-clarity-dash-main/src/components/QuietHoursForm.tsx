import { useState } from "react";
import { useTranslation } from "react-i18next";

import { localeOf } from "../lib/formatTimestamp";
import { usePreferences } from "../lib/usePreferences";
import type { QuietHours } from "../types/settings";
import { button, field } from "./variants";

const ISO_WEEK = [1, 2, 3, 4, 5, 6, 7] as const;
// 1 January 2024 was a Monday, so day n of that week is ISO weekday n.
const MONDAY_2024 = Date.UTC(2024, 0, 1);
const MS_PER_DAY = 86_400_000;
const ZONES = [
  "Asia/Kuala_Lumpur",
  "Asia/Singapore",
  "Asia/Jakarta",
  "Asia/Bangkok",
  "Asia/Hong_Kong",
  "Asia/Tokyo",
  "Australia/Sydney",
  "Europe/London",
  "America/New_York",
];

function weekdayName(isoDay: number, locale: string): string {
  return new Date(MONDAY_2024 + (isoDay - 1) * MS_PER_DAY).toLocaleDateString(locale, {
    weekday: "short",
    timeZone: "UTC",
  });
}

type QuietHoursFormProps = {
  initial: QuietHours;
  isSaving: boolean;
  onSave: (hours: QuietHours) => void;
};

/** A quiet window and the days quiet all day; shared by Settings and the admin console. */
export default function QuietHoursForm({ initial, isSaving, onSave }: QuietHoursFormProps) {
  const { t } = useTranslation();
  const locale = localeOf(usePreferences().preferences.language);
  const [hours, setHours] = useState(initial);
  const zones = Array.from(new Set([hours.timezone, ...ZONES]));
  const toggleDay = (day: number) =>
    setHours({
      ...hours,
      weekendDays: hours.weekendDays.includes(day)
        ? hours.weekendDays.filter((d) => d !== day)
        : [...hours.weekendDays, day],
    });
  const isValid = hours.start.slice(0, 5) !== hours.end.slice(0, 5);

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        onSave(hours);
      }}
    >
      <div className="flex flex-wrap gap-3">
        <label className="space-y-1">
          <span className="block text-xs font-medium text-fg-muted">{t("quietHours.from")}</span>
          <input
            type="time"
            value={hours.start.slice(0, 5)}
            onChange={(event) => setHours({ ...hours, start: event.target.value })}
            className={field({ size: "sm" })}
          />
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-fg-muted">{t("quietHours.to")}</span>
          <input
            type="time"
            value={hours.end.slice(0, 5)}
            onChange={(event) => setHours({ ...hours, end: event.target.value })}
            className={field({ size: "sm" })}
          />
        </label>
        <label className="space-y-1">
          <span className="block text-xs font-medium text-fg-muted">
            {t("quietHours.timezone")}
          </span>
          <select
            value={hours.timezone}
            onChange={(event) => setHours({ ...hours, timezone: event.target.value })}
            className={field({ size: "sm" })}
          >
            {zones.map((zone) => (
              <option key={zone} value={zone}>
                {zone}
              </option>
            ))}
          </select>
        </label>
      </div>
      <fieldset>
        <legend className="text-xs font-medium text-fg-muted">{t("quietHours.weekend")}</legend>
        <div className="mt-1 flex flex-wrap gap-3">
          {ISO_WEEK.map((day) => (
            <label
              key={day}
              className="flex min-h-11 items-center gap-1 text-sm text-fg md:min-h-0"
            >
              <input
                type="checkbox"
                checked={hours.weekendDays.includes(day)}
                onChange={() => toggleDay(day)}
                className="size-4 accent-[var(--brand)]"
              />
              {weekdayName(day, locale)}
            </label>
          ))}
        </div>
        <p className="mt-1 text-xs text-fg-subtle">{t("quietHours.weekendHint")}</p>
      </fieldset>
      {isValid ? null : <p className="text-xs text-danger">{t("quietHours.sameTimes")}</p>}
      <button
        type="submit"
        disabled={!isValid || isSaving}
        className={button({ intent: "primary", size: "sm" })}
      >
        {isSaving ? t("quietHours.saving") : t("quietHours.save")}
      </button>
    </form>
  );
}
