import { describe, expect, test } from "vitest";

import {
  isQuiet,
  minutesOf,
  nextMondayHere,
  nextQuietEnd,
  quietSuggestion,
  zoneOffsetMinutes,
  type QuietHours,
} from "../quietHours";

const HOURS: QuietHours = {
  start: "21:00:00",
  end: "08:00:00",
  weekendDays: [6, 7],
  timezone: "Asia/Kuala_Lumpur",
};
const MYT = 480;

describe("quiet hours", () => {
  test("cover the evening and the early morning, and all of a weekend day", () => {
    expect(minutesOf("21:30:00")).toBe(1290);
    expect(isQuiet({ weekday: 2, minutes: minutesOf("23:40") }, HOURS)).toBe(true);
    expect(isQuiet({ weekday: 2, minutes: minutesOf("07:59") }, HOURS)).toBe(true);
    expect(isQuiet({ weekday: 2, minutes: minutesOf("08:00") }, HOURS)).toBe(false);
    expect(isQuiet({ weekday: 6, minutes: minutesOf("12:00") }, HOURS)).toBe(true);
  });

  test("a window that does not cross midnight is quiet only inside it", () => {
    const lunch = { ...HOURS, start: "12:00:00", end: "13:00:00", weekendDays: [] };
    expect(isQuiet({ weekday: 3, minutes: minutesOf("12:30") }, lunch)).toBe(true);
    expect(isQuiet({ weekday: 3, minutes: minutesOf("13:30") }, lunch)).toBe(false);
  });

  test("a late Tuesday evening suggests Wednesday 8am on their clock", () => {
    // Tue 7 Oct 2026, 23:40 in Kuala Lumpur
    const now = new Date("2026-10-07T15:40:00Z");
    const suggestion = quietSuggestion(now, MYT, HOURS);
    expect(suggestion?.sendAt.toISOString()).toBe("2026-10-08T00:00:00.000Z");
    expect(suggestion?.isTheirTime).toBe(true);
  });

  test("a Friday night skips the weekend to Monday 8am", () => {
    const now = new Date("2026-10-09T14:00:00Z"); // Fri 22:00 MYT
    expect(nextQuietEnd(now, MYT, HOURS)?.toISOString()).toBe("2026-10-12T00:00:00.000Z");
  });

  test("Kelantan's Friday-Saturday weekend sends on Sunday", () => {
    const kelantan = { ...HOURS, weekendDays: [5, 6] };
    const now = new Date("2026-10-08T14:00:00Z"); // Thu 22:00 MYT
    expect(nextQuietEnd(now, MYT, kelantan)?.toISOString()).toBe("2026-10-11T00:00:00.000Z");
  });

  test("working hours for them need no suggestion", () => {
    expect(quietSuggestion(new Date("2026-10-07T03:00:00Z"), MYT, HOURS)).toBeNull();
  });

  test("an unknown offset falls back to the reader's own zone and says so", () => {
    const suggestion = quietSuggestion(new Date("2026-10-07T15:40:00Z"), null, HOURS);
    expect(suggestion?.isTheirTime).toBe(false);
    expect(zoneOffsetMinutes("Asia/Kuala_Lumpur", new Date("2026-10-07T15:40:00Z"))).toBe(MYT);
  });

  test("next Monday is never today", () => {
    const monday = new Date(2026, 9, 12, 7, 0); // Monday 07:00 local
    expect(nextMondayHere(monday, 9).getDate()).toBe(19);
  });
});
