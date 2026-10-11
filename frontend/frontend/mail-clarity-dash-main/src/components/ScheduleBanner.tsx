import { CalendarClock, CircleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useFormat } from "../lib/useFormat";
import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import type { Email } from "../types/email";
import { button } from "./variants";

type ScheduleBannerProps = { email: Email; workflow: DraftWorkflow };

/** A reply waiting to go out, or why the last one was called off. */
export default function ScheduleBanner({ email, workflow }: ScheduleBannerProps) {
  const { t } = useTranslation();
  const format = useFormat();
  if (email.scheduledFor) {
    return (
      <div
        role="status"
        className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line bg-surface-muted px-3 py-2 text-sm text-fg"
      >
        <span className="flex items-center gap-2">
          <CalendarClock aria-hidden className="size-4 text-fg-muted" />
          {t("schedule.scheduledFor", { when: format.timestamp(email.scheduledFor) })}
        </span>
        <button
          type="button"
          disabled={workflow.isScheduling}
          onClick={workflow.cancelSchedule}
          className={button({ size: "xs" })}
        >
          {t("schedule.cancel")}
        </button>
      </div>
    );
  }
  if (email.scheduleCancelled && !email.sentAt) {
    return (
      <p
        role="alert"
        className="flex gap-2 rounded-md border border-warning-line bg-warning-soft p-3 text-sm text-warning"
      >
        <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
        {t(`schedule.cancelled.${email.scheduleCancelled}`)}
      </p>
    );
  }
  return null;
}
