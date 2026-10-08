import { CircleAlert, CircleCheck, CircleHelp, Hash } from "lucide-react";
import { useTranslation } from "react-i18next";

import { actionLabel } from "../../lib/auditTrail";
import { useFormat } from "../../lib/useFormat";
import type { AuditTrailEvent } from "../../types/audit";
import FieldList from "./FieldList";
import VerificationBadge from "./VerificationBadge";

const HASH_HEAD = 6;
const HASH_TAIL = 4;

type AuditTableProps = { events: AuditTrailEvent[]; onInspect: (event: AuditTrailEvent) => void };

export default function AuditTable({ events, onInspect }: AuditTableProps) {
  const { t } = useTranslation();
  return (
    <div className="relative max-h-[34rem] overflow-auto rounded-lg border border-line bg-surface">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 z-10 border-b border-line bg-surface-muted text-xs uppercase tracking-wider text-fg-muted">
          <tr>
            <th className="px-4 py-3 font-semibold">{t("audit.headers.timestamp")}</th>
            <th className="px-4 py-3 font-semibold">{t("audit.headers.action")}</th>
            <th className="px-4 py-3 font-semibold">{t("audit.headers.status")}</th>
            <th className="px-4 py-3 font-semibold">{t("audit.headers.detail")}</th>
            <th className="px-4 py-3 text-right font-semibold">{t("audit.headers.proof")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line-subtle">
          {events.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-sm text-fg-subtle">
                {t("audit.empty")}
              </td>
            </tr>
          ) : (
            events.map((event) => <AuditRow key={event.id} event={event} onInspect={onInspect} />)
          )}
        </tbody>
      </table>
    </div>
  );
}

function AuditRow({
  event,
  onInspect,
}: {
  event: AuditTrailEvent;
  onInspect: AuditTableProps["onInspect"];
}) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <tr className="align-top hover:bg-surface-muted">
      <td className="whitespace-nowrap px-4 py-3 text-xs text-fg-muted">
        {format.timestamp(event.createdAt)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-xs font-medium text-fg-body">
        {actionLabel(event.action, t)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-xs">
        <Outcome success={event.success} />
      </td>
      <td className="max-w-md px-4 py-3 text-xs">
        <FieldList fields={event.fields} />
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-right">
        <button
          type="button"
          onClick={() => onInspect(event)}
          aria-label={t("audit.inspect")}
          className="inline-flex items-center gap-1.5 rounded border border-line bg-surface-muted px-2 py-1 font-mono text-[11px] text-fg-muted hover:border-brand hover:text-brand focus-visible:outline-2 focus-visible:outline-brand"
        >
          <Hash aria-hidden className="size-3" />
          {event.currentHash ? <ShortHash hash={event.currentHash} /> : null}
          <VerificationBadge verification={event.verification} />
        </button>
      </td>
    </tr>
  );
}

function ShortHash({ hash }: { hash: string }) {
  const { t } = useTranslation();
  return (
    <span>
      {t("audit.shortHash", { head: hash.slice(0, HASH_HEAD), tail: hash.slice(-HASH_TAIL) })}
    </span>
  );
}

function Outcome({ success }: { success: boolean | null }) {
  const { t } = useTranslation();
  if (success === null) {
    return (
      <span className="inline-flex items-center gap-1 text-fg-muted">
        <CircleHelp aria-hidden className="size-3.5" />
        {t("audit.status.unknown")}
      </span>
    );
  }
  if (!success) {
    return (
      <span className="inline-flex items-center gap-1 text-danger">
        <CircleAlert aria-hidden className="size-3.5" />
        {t("audit.status.failed")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-success">
      <CircleCheck aria-hidden className="size-3.5" />
      {t("audit.status.passed")}
    </span>
  );
}
