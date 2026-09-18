/** Formats an ISO 8601 timestamp for compact display in the inbox / detail header. */
export function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;

  // No timeZone override: timestamps arrive UTC-aware from the API, and a reader wants the time
  // the mail arrived for them. Forcing UTC showed every email 8 hours out in Malaysia.
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
