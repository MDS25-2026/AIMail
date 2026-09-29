import { usePreferences } from "../components/PreferencesProvider";
import { formatNumber, formatTimestamp } from "./formatTimestamp";

/** Formatters bound to the reader's language, so no component passes the language by hand. */
export function useFormat() {
  const { language } = usePreferences().preferences;
  return {
    timestamp: (iso: string) => formatTimestamp(iso, language),
    number: (value: number) => formatNumber(value, language),
  };
}
