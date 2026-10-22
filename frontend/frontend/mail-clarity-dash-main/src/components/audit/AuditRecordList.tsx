import { CircleAlert, CircleCheck, CircleHelp, Hash } from "lucide-react";
import { useTranslation } from "react-i18next";

import { actionLabel } from "../../lib/auditTrail";
import { useFormat } from "../../lib/useFormat";
import type { ActionGroup, AuditTrailEvent } from "../../types/audit";
import FieldList from "./FieldList";
import VerificationBadge from "./VerificationBadge";

const HASH_HEAD = 6;
const HASH_TAIL = 4;

type AuditRecordListProps = {
  events: AuditTrailEvent[];
  onInspect: (event: AuditTrailEvent) => void;
};

/** One record per row: when, who, what in plain words, how it ended, and its hash check. */
export default function AuditRecordList({ events, onInspect }: AuditRecordListProps) {
  const { t } = useTranslation();
  if (events.length === 0) {
    return (
      <p className="rounded-lg border border-line bg-surface px-4 py-8 text-center text-sm text-fg-subtle">
        {t("audit.noMatches")}
      </p>
    );
  }
  return (
    <ul className="relative divide-y divide-line-subtle overflow-hidden rounded-lg border border-line bg-surface">
      {events.map((event) => (
        <AuditRecord key={event.id} event={event} onInspect={onInspect} />
      ))}
    </ul>
  );
}

function AuditRecord({
  event,
  onInspect,
}: {
  event: AuditTrailEvent;
  onInspect: AuditRecordListProps["onInspect"];
}) {
  const { t } = useTranslation();
  const format = useFormat();
  // No person: a system event (the listener, a job) or an account since deleted.
  const person = event.userEmail ?? t("audit.system");
  return (
    <li className="grid gap-2 px-4 py-3 hover:bg-surface-muted md:grid-cols-[11rem_minmax(0,1fr)_auto] md:gap-4">
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 text-xs md:block">
        <time dateTime={event.createdAt} className="text-fg-muted">
          {format.timestamp(event.createdAt)}
        </time>
        <p className="truncate font-medium text-fg-body" title={person}>
          {person}
        </p>
      </div>
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-sm font-medium text-fg">{actionLabel(event.action, t)}</span>
          <GroupTag group={event.group} />
          <Outcome success={event.success} />
        </div>
        <div className="text-xs">
          <FieldList fields={event.fields} />
        </div>
      </div>
      <div className="md:text-right">
        <button
          type="button"
          onClick={() => onInspect(event)}
          aria-label={t("audit.inspect")}
          className="inline-flex min-h-11 items-center gap-1.5 rounded border border-line bg-surface-muted px-2 py-1 font-mono text-[11px] text-fg-muted hover:border-brand hover:text-brand focus-visible:outline-2 focus-visible:outline-brand md:min-h-0"
        >
          <Hash aria-hidden className="size-3" />
          {event.currentHash ? <ShortHash hash={event.currentHash} /> : null}
          <VerificationBadge verification={event.verification} />
        </button>
      </div>
    </li>
  );
}

function GroupTag({ group }: { group: ActionGroup }) {
  const { t } = useTranslation();
  return (
    <span className="rounded border border-line bg-surface-muted px-1.5 py-0.5 text-[11px] font-medium text-fg-muted">
      {t(`audit.groups.${group}`)}
    </span>
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
      <span className="inline-flex items-center gap-1 text-xs text-fg-muted">
        <CircleHelp aria-hidden className="size-3.5" />
        {t("audit.status.unknown")}
      </span>
    );
  }
  if (!success) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-danger">
        <CircleAlert aria-hidden className="size-3.5" />
        {t("audit.status.failed")}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-success">
      <CircleCheck aria-hidden className="size-3.5" />
      {t("audit.status.passed")}
    </span>
  );
}
