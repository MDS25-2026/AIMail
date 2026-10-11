/**
 * Quiet hours (specs/features/quiet-hours-send-later.md): is it late for the person receiving the
 * reply, and when do their quiet hours end. A suggestion only; nothing here blocks a send.
 *
 * Their time comes from the offset in their last email's Date header. Without one, the reader's own
 * quiet-hours timezone stands in, and the suggestion says "your time".
 */
import type { Schemas } from "../types/schema";

export type QuietHours = Schemas["QuietHoursView"];

const MINUTES_PER_DAY = 24 * 60;
const MS_PER_MINUTE = 60_000;
const SUNDAY_JS = 0;
const SUNDAY_ISO = 7;
// Far enough to cross any weekend twice; a week with every day quiet has no next end.
const MAX_DAYS_AHEAD = 14;

/** A moment on someone's clock: ISO weekday (1 = Monday) and minutes after midnight. */
type Clock = { weekday: number; minutes: number };

/** "21:00:00" or "21:00" -> 1260. */
export function minutesOf(time: string): number {
  const [hours = "0", minutes = "0"] = time.split(":");
  return Number(hours) * 60 + Number(minutes);
}

function isoWeekday(jsDay: number): number {
  return jsDay === SUNDAY_JS ? SUNDAY_ISO : jsDay;
}

/** The zone's offset from UTC at that instant, in minutes (+480 for Kuala Lumpur). */
export function zoneOffsetMinutes(timeZone: string, at: Date): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
  }).formatToParts(at);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((p) => p.type === type)?.value ?? 0);
  const asUtc = Date.UTC(
    part("year"),
    part("month") - 1,
    part("day"),
    part("hour"),
    part("minute"),
  );
  return Math.round(
    (asUtc - Math.floor(at.getTime() / MS_PER_MINUTE) * MS_PER_MINUTE) / MS_PER_MINUTE,
  );
}

/** Shifts an instant so its UTC fields read as the local clock at that offset. */
function shifted(at: Date, offsetMinutes: number): Date {
  return new Date(at.getTime() + offsetMinutes * MS_PER_MINUTE);
}

function clockAt(at: Date, offsetMinutes: number): Clock {
  const local = shifted(at, offsetMinutes);
  return {
    weekday: isoWeekday(local.getUTCDay()),
    minutes: local.getUTCHours() * 60 + local.getUTCMinutes(),
  };
}

/** Quiet all day on weekend days; otherwise between start and end, which may cross midnight. */
export function isQuiet(clock: Clock, hours: QuietHours): boolean {
  if (hours.weekendDays.includes(clock.weekday)) return true;
  const start = minutesOf(hours.start);
  const end = minutesOf(hours.end);
  return start > end
    ? clock.minutes >= start || clock.minutes < end
    : clock.minutes >= start && clock.minutes < end;
}

/** The next moment quiet hours end on a day that is not a weekend day, or null if there is none. */
export function nextQuietEnd(now: Date, offsetMinutes: number, hours: QuietHours): Date | null {
  const local = shifted(now, offsetMinutes);
  const midnight = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate());
  const end = minutesOf(hours.end);
  for (let day = 0; day <= MAX_DAYS_AHEAD; day += 1) {
    const localEnd = midnight + (day * MINUTES_PER_DAY + end) * MS_PER_MINUTE;
    const instant = new Date(localEnd - offsetMinutes * MS_PER_MINUTE);
    const isWeekend = hours.weekendDays.includes(isoWeekday(new Date(localEnd).getUTCDay()));
    if (instant > now && !isWeekend) return instant;
  }
  return null;
}

export type QuietSuggestion = {
  /** Their clock now, for "It's 11:40pm for them". */
  theirNow: Date;
  /** When to send instead: the end of their quiet hours. */
  sendAt: Date;
  /** Their offset, for showing both times on their clock. */
  offsetMinutes: number;
  /** False when their offset is unknown and the reader's own timezone was used. */
  isTheirTime: boolean;
};

/** A suggestion when it is quiet hours for the recipient now; null when it is fine to send. */
export function quietSuggestion(
  now: Date,
  senderOffsetMinutes: number | null | undefined,
  hours: QuietHours,
): QuietSuggestion | null {
  const isTheirTime = senderOffsetMinutes !== null && senderOffsetMinutes !== undefined;
  const offsetMinutes = isTheirTime ? senderOffsetMinutes : zoneOffsetMinutes(hours.timezone, now);
  if (!isQuiet(clockAt(now, offsetMinutes), hours)) return null;
  const sendAt = nextQuietEnd(now, offsetMinutes, hours);
  return sendAt ? { theirNow: now, sendAt, offsetMinutes, isTheirTime } : null;
}

/** A time on a clock at a fixed offset, such as "11:40 pm", in the reader's language. */
export function clockLabel(at: Date, offsetMinutes: number, locale: string): string {
  return shifted(at, offsetMinutes).toLocaleTimeString(locale, {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

/** The next given hour on the reader's own clock, today if still ahead, else tomorrow. */
export function nextHourHere(now: Date, hour: number, daysAhead: number): Date {
  const at = new Date(now);
  at.setDate(at.getDate() + daysAhead);
  at.setHours(hour, 0, 0, 0);
  return at;
}

/** The next Monday at that hour on the reader's own clock. */
export function nextMondayHere(now: Date, hour: number): Date {
  const daysToMonday = (8 - isoWeekday(now.getDay())) % 7 || 7;
  return nextHourHere(now, hour, daysToMonday);
}
