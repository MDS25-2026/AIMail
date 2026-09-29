import { CircleAlert, CircleCheck, CircleHelp } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useFormat } from "../../lib/useFormat";
import type { AuditEvent } from "../../types/admin";

export default function AuditTable({ events }: { events: AuditEvent[] }) {
  const { t } = useTranslation();
  const format = useFormat();
  if (events.length === 0) return <p className="text-sm text-fg-subtle">{t("admin.noData")}</p>;

  return (
    <div className="max-h-[28rem] overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 border-b border-line bg-surface text-xs uppercase tracking-wide text-fg-muted">
          <tr>
            <th className="py-2 pr-4 font-semibold">{t("admin.time")}</th>
            <th className="py-2 pr-4 font-semibold">{t("admin.action")}</th>
            <th className="py-2 pr-4 font-semibold">{t("admin.result")}</th>
            <th className="py-2 font-semibold">{t("admin.detail")}</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event, index) => (
            <tr
              key={`${event.created_at}-${index}`}
              className="border-b border-line-subtle align-top last:border-0"
            >
              <td className="whitespace-nowrap py-2 pr-4 text-fg-muted">
                {format.timestamp(event.created_at)}
              </td>
              <td className="py-2 pr-4 font-mono text-xs text-fg-body">{event.action}</td>
              <td className="py-2 pr-4">
                {event.success === null ? (
                  <span className="inline-flex items-center gap-1 text-fg-muted">
                    <CircleHelp aria-hidden className="size-3.5" />
                    {t("admin.unknown")}
                  </span>
                ) : event.success === false ? (
                  <span className="inline-flex items-center gap-1 text-danger">
                    <CircleAlert aria-hidden className="size-3.5" />
                    {t("admin.failed")}
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-success">
                    <CircleCheck aria-hidden className="size-3.5" />
                    {t("admin.ok")}
                  </span>
                )}
              </td>
              <td className="break-all py-2 font-mono text-xs text-fg-muted">{event.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
