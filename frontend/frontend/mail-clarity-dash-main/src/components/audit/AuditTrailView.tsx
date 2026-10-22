import { Download, Search } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { matchesQuery } from "../../lib/auditTrail";
import { useAuditTrail } from "../../lib/queries";
import { cn } from "../../lib/utils";
import {
  NO_AUDIT_FILTERS,
  type AuditFilters,
  type AuditTrail,
  type AuditTrailEvent,
} from "../../types/audit";
import { PageError, PageLoading } from "../PageState";
import { button, field } from "../variants";
import AuditFilterBar from "./AuditFilterBar";
import AuditRecordList from "./AuditRecordList";
import IntegrityBanner from "./IntegrityBanner";
import ProofDialog from "./ProofDialog";

const PAGE_SIZE = 50;
// GET /audit answers at most this many rows (backend/app/audit_routes.py MAX_EVENTS).
const MAX_ROWS = 100;
const EXPORT_NAME = "aimail-audit-trail";
const DATE_LENGTH = 10;

/** The reader's own copy of the trail, to keep or hand to someone checking it. */
function downloadJson(trail: AuditTrail): void {
  const blob = new Blob([JSON.stringify(trail, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${EXPORT_NAME}-${new Date().toISOString().slice(0, DATE_LENGTH)}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

/** Everyone's records for an admin: the chain check, a summary, filters, then the records. */
export default function AuditTrailView() {
  const { t } = useTranslation();
  const [filters, setFilters] = useState<AuditFilters>(NO_AUDIT_FILTERS);
  const [limit, setLimit] = useState(PAGE_SIZE);
  const trail = useAuditTrail(filters, limit);
  // New filters start again from the first page.
  const changeFilters = (next: AuditFilters) => {
    setFilters(next);
    setLimit(PAGE_SIZE);
  };
  const canLoadMore =
    trail.data !== undefined &&
    trail.data.events.length < Math.min(trail.data.totalRecords, MAX_ROWS);

  return (
    <div className="space-y-4">
      {trail.data ? <IntegrityBanner trail={trail.data} /> : null}
      {trail.data ? <Summary trail={trail.data} /> : null}
      {/* Outside the loading states, so a failed filter can still be changed back. */}
      <AuditFilterBar
        filters={filters}
        people={trail.data?.people ?? []}
        onChange={changeFilters}
      />
      {trail.isPending ? <PageLoading label={t("audit.title")} /> : null}
      {trail.isError ? (
        <PageError
          label={t("audit.title")}
          error={trail.error}
          onRetry={() => void trail.refetch()}
        />
      ) : null}
      {trail.data && !trail.isError ? (
        <Records
          trail={trail.data}
          onLoadMore={
            canLoadMore ? () => setLimit((prev) => Math.min(prev + PAGE_SIZE, MAX_ROWS)) : undefined
          }
        />
      ) : null}
    </div>
  );
}

function Summary({ trail }: { trail: AuditTrail }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p aria-live="polite" className="text-sm font-medium text-fg">
        {t("audit.summary", {
          records: t("audit.recordCount", { count: trail.totalRecords }),
          failures: t("audit.failureCount", { count: trail.failedRecords }),
        })}
      </p>
      <button
        type="button"
        onClick={() => downloadJson(trail)}
        className={cn(button({ intent: "quiet", size: "xs" }), "inline-flex items-center gap-1.5")}
      >
        <Download aria-hidden className="size-3.5" />
        {t("audit.exportJson")}
      </button>
    </div>
  );
}

function Records({ trail, onLoadMore }: { trail: AuditTrail; onLoadMore?: () => void }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [inspected, setInspected] = useState<AuditTrailEvent | null>(null);
  const shown = trail.events.filter((event) => matchesQuery(event, query));
  return (
    <>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <label className="relative w-full max-w-sm">
          <span className="sr-only">{t("audit.filterLabel")}</span>
          <Search
            aria-hidden
            className="pointer-events-none absolute left-3 top-2.5 size-4 text-fg-muted"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("audit.filterPlaceholder")}
            className={cn(field({ size: "sm" }), "w-full py-1.5 pl-9 text-xs")}
          />
        </label>
        <p className="text-xs text-fg-muted">
          {t("audit.showing", { shown: shown.length, total: trail.totalRecords })}
        </p>
      </div>
      <AuditRecordList events={shown} onInspect={setInspected} />
      {onLoadMore ? (
        <div className="flex justify-center pt-2">
          <button
            type="button"
            onClick={onLoadMore}
            className={cn(button({ intent: "quiet", size: "sm" }), "text-xs")}
          >
            {t("audit.loadMore")}
          </button>
        </div>
      ) : null}
      <ProofDialog event={inspected} onClose={() => setInspected(null)} />
    </>
  );
}
