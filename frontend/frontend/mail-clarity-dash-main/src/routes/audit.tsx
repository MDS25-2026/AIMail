import { createFileRoute } from "@tanstack/react-router";
import { Download, Search } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import AuditTable from "../components/audit/AuditTable";
import IntegrityBanner from "../components/audit/IntegrityBanner";
import ProofDialog from "../components/audit/ProofDialog";
import { PageError, PageLoading } from "../components/PageState";
import { button, field } from "../components/variants";
import { matchesQuery } from "../lib/auditTrail";
import { Page, pageMeta } from "../lib/pageMeta";
import { useAuditTrail } from "../lib/queries";
import { cn } from "../lib/utils";
import type { AuditTrail, AuditTrailEvent } from "../types/audit";

export const Route = createFileRoute("/audit")({
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Audit) }),
  component: AuditPage,
});

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

function AuditPage() {
  const { t } = useTranslation();
  const trail = useAuditTrail();
  return (
    <AppShell>
      <section className="relative min-w-0 flex-1 overflow-y-auto bg-surface-muted p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-fg">{t("audit.title")}</h1>
              <p className="text-sm text-fg-muted">{t("audit.subtitle")}</p>
            </div>
            {trail.data ? <ExportButton trail={trail.data} /> : null}
          </header>
          {trail.isPending ? <PageLoading label={t("audit.title")} /> : null}
          {trail.isError ? (
            <PageError
              label={t("audit.title")}
              error={trail.error}
              onRetry={() => void trail.refetch()}
            />
          ) : null}
          {trail.data ? <TrailView trail={trail.data} /> : null}
        </div>
      </section>
    </AppShell>
  );
}

function ExportButton({ trail }: { trail: AuditTrail }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={() => downloadJson(trail)}
      className={cn(
        button({ intent: "quiet", size: "xs" }),
        "inline-flex items-center gap-1.5 self-start",
      )}
    >
      <Download aria-hidden className="size-3.5" />
      {t("audit.exportJson")}
    </button>
  );
}

function TrailView({ trail }: { trail: AuditTrail }) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const [inspected, setInspected] = useState<AuditTrailEvent | null>(null);
  const shown = trail.events.filter((event) => matchesQuery(event, query));
  return (
    <>
      <IntegrityBanner trail={trail} />
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
          {t("audit.showing", { shown: shown.length, total: trail.events.length })}
        </p>
      </div>
      <AuditTable events={shown} onInspect={setInspected} />
      <ProofDialog event={inspected} onClose={() => setInspected(null)} />
    </>
  );
}
