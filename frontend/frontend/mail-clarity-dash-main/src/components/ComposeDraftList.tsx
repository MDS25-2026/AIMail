import { Link } from "@tanstack/react-router";
import { CircleAlert, LoaderCircle, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { detailValues, maskSender } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { useDetailsHidden } from "../lib/detailsVisibility";
import { useComposeSendFailure } from "../lib/queries";
import { useFormat } from "../lib/useFormat";
import { ComposeState, type ComposeList, type ComposeSummary } from "../types/compose";
import WithDetails from "./WithDetails";

type ComposeDraftListProps = { list: ComposeList; selectedId: string | undefined };

/** The user's drafts, newest first, then what they sent recently. */
export default function ComposeDraftList({ list, selectedId }: ComposeDraftListProps) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4 px-2 pb-4">
      <DraftSection title={t("compose.draftsTitle")} rows={list.drafts} selectedId={selectedId} />
      <DraftSection title={t("compose.sentTitle")} rows={list.sent} selectedId={selectedId} />
    </div>
  );
}

type DraftSectionProps = { title: string; rows: ComposeSummary[]; selectedId: string | undefined };

function DraftSection({ title, rows, selectedId }: DraftSectionProps) {
  if (rows.length === 0) return null;
  return (
    <section aria-label={title}>
      <h2 className="px-2 text-xs font-semibold uppercase tracking-wide text-fg-subtle">{title}</h2>
      <ul className="mt-1 space-y-0.5">
        {rows.map((row) => (
          // Each row fills in its own draft's details, as the inbox rows do.
          <DetailsContext.Provider key={row.id} value={detailValues(row.details)}>
            <DraftRow row={row} isSelected={row.id === selectedId} />
          </DetailsContext.Provider>
        ))}
      </ul>
    </section>
  );
}

function DraftRow({ row, isSelected }: { row: ComposeSummary; isSelected: boolean }) {
  const { t } = useTranslation();
  const format = useFormat();
  const [isHidden] = useDetailsHidden();
  const recipients = row.to.map((address) => maskSender(address, isHidden)).join(", ");
  // A send that failed after its editor closed, so its draft says so here too.
  const hasFailedSend =
    Boolean(useComposeSendFailure(row.id).data) && row.state === ComposeState.Draft;
  return (
    <li>
      <Link
        to="/compose"
        search={{ draft: row.id }}
        aria-current={isSelected ? "page" : undefined}
        className={`block rounded-md px-2 py-2 transition-colors ${
          isSelected ? "bg-brand-soft" : "hover:bg-surface-muted"
        }`}
      >
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-semibold text-fg">
            {row.subject ? <WithDetails text={row.subject} /> : t("compose.noSubject")}
          </span>
          <span className="shrink-0 text-xs text-fg-subtle">
            {format.timestamp(row.sentAt ?? row.updatedAt)}
          </span>
        </span>
        <span className="block truncate text-xs text-fg-muted">
          {recipients ? t("compose.toList", { recipients }) : t("compose.noRecipients")}
        </span>
        {row.preview ? (
          <span className="block truncate text-xs text-fg-subtle">
            <WithDetails text={row.preview} />
          </span>
        ) : null}
        <StateBadge state={row.state} />
        {hasFailedSend ? (
          <span className="mt-1 inline-flex items-center gap-1 rounded bg-danger-soft px-1.5 text-xs font-medium text-danger">
            <CircleAlert aria-hidden className="size-3" />
            {t("compose.notSent")}
          </span>
        ) : null}
      </Link>
    </li>
  );
}

/** Icon and words, so the state never rests on colour alone. */
function StateBadge({ state }: { state: ComposeState }) {
  const { t } = useTranslation();
  if (state === ComposeState.Sending) {
    return (
      <span className="mt-1 inline-flex items-center gap-1 text-xs text-fg-muted">
        <LoaderCircle aria-hidden className="size-3" />
        {t("compose.state.sending")}
      </span>
    );
  }
  if (state === ComposeState.OutcomeUnknown) {
    return (
      <span className="mt-1 inline-flex items-center gap-1 rounded bg-warning-soft px-1.5 text-xs font-medium text-warning">
        <TriangleAlert aria-hidden className="size-3" />
        {t("compose.state.outcomeUnknown")}
      </span>
    );
  }
  return null;
}
