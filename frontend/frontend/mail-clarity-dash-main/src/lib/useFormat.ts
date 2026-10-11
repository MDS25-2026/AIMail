import { usePreferences } from "../lib/usePreferences";
import { formatNumber, formatTimestamp, localeOf } from "./formatTimestamp";
import { clockLabel } from "./quietHours";

/** Formatters bound to the reader's language, so no component passes the language by hand. */
export function useFormat() {
  const { language } = usePreferences().preferences;
  return {
    timestamp: (iso: string) => formatTimestamp(iso, language),
    number: (value: number) => formatNumber(value, language),
    /** A time on a clock at a fixed offset from UTC, such as the recipient's. */
    clock: (at: Date, offsetMinutes: number) => clockLabel(at, offsetMinutes, localeOf(language)),
  };
}
