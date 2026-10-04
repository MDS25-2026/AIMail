import { Language } from "./preferences";

/** Malaysia-first regional variants: day-first dates, and the reader's own script. */
const LOCALE: Record<Language, string> = {
  [Language.English]: "en-MY",
  [Language.Malay]: "ms-MY",
  [Language.Chinese]: "zh-CN",
};

/** Formats an ISO 8601 timestamp for compact display in the inbox / detail header. */
export function formatTimestamp(iso: string, language: Language = Language.English): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;

  // No timeZone override: timestamps arrive UTC-aware from the API, and a reader wants the time
  // the mail arrived for them. Forcing UTC showed every email 8 hours out in Malaysia.
  return date.toLocaleString(LOCALE[language], {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatNumber(value: number, language: Language = Language.English): string {
  return value.toLocaleString(LOCALE[language], { maximumFractionDigits: 3 });
}
