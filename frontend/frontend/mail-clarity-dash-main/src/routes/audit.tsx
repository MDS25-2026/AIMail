import { createFileRoute } from "@tanstack/react-router";
import {
  Check,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  Copy,
  Download,
  Hash,
  Link as LinkIcon,
  Search,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import { PageError, PageLoading } from "../components/PageState";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import type { AuditLogEvent } from "../lib/api";
import { useAuditTrail } from "../lib/queries";
import { useFormat } from "../lib/useFormat";

export const Route = createFileRoute("/audit")({
  head: () => ({
    meta: [
      { title: "AIMail Audit Trail" },
      {
        name: "description",
        content: "Cryptographic, tamper-evident PDPA compliance audit ledger.",
      },
    ],
  }),
  component: AuditPage,
});

function AuditPage() {
  const { t } = useTranslation();
  const format = useFormat();
  const { data, isPending, isError, error, refetch } = useAuditTrail();

  const [selectedEvent, setSelectedEvent] = useState<AuditLogEvent | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [filterQuery, setFilterQuery] = useState("");

  const copyToClipboard = (text: string, field: string) => {
    void navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleExportJson = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `aimail-audit-trail-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredEvents = useMemo(() => {
    if (!data?.events) return [];
    if (!filterQuery.trim()) return data.events;
    const q = filterQuery.toLowerCase();
    return data.events.filter(
      (ev) =>
        ev.action.toLowerCase().includes(q) ||
        ev.detail.toLowerCase().includes(q) ||
        ev.id.toLowerCase().includes(q) ||
        (ev.current_hash && ev.current_hash.toLowerCase().includes(q)),
    );
  }, [data?.events, filterQuery]);

  const getActionLabel = (action: string) => {
    switch (action) {
      case "generate_draft":
        return t("audit.actions.generate_draft");
      case "store_message":
        return t("audit.actions.store_message");
      case "pii_mask":
        return t("audit.actions.pii_mask");
      case "approve_and_send":
        return t("audit.actions.approve_and_send");
      case "quarantine":
        return t("audit.actions.quarantine");
      default:
        return action;
    }
  };

  const formatSummary = (detail: string, action: string) => {
    if (!detail) return "Standard operation completed";
    if (detail.includes("message=") && detail.includes("tone=")) {
      const toneMatch = detail.match(/tone=([a-z]+)/);
      const confMatch = detail.match(/confidence=([0-9.]+)/);
      const tone = toneMatch ? toneMatch[1] : "default";
      const conf = confMatch ? Math.round(Number.parseFloat(confMatch[1]) * 100) : 95;
      return `Draft generated (tone: ${tone}, confidence: ${conf}%)`;
    }
    if (detail.includes("Masked")) {
      return detail;
    }
    return detail;
  };

  return (
    <AppShell>
      <section className="relative min-w-0 flex-1 overflow-y-auto bg-surface-muted p-6">
        <div className="mx-auto max-w-6xl space-y-6">
          {/* Header */}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-fg-header">
                {t("audit.title")}
              </h1>
              <p className="text-sm text-fg-muted">{t("audit.subtitle")}</p>
            </div>
            {data ? (
              <button
                type="button"
                onClick={handleExportJson}
                className="inline-flex items-center gap-1.5 self-start rounded-md border border-line bg-surface px-3 py-1.5 text-xs font-medium text-fg-body shadow-sm hover:bg-surface-hover hover:text-fg-header focus:outline-none focus:ring-2 focus:ring-accent"
              >
                <Download className="size-3.5" />
                <span>{t("audit.exportJson")}</span>
              </button>
            ) : null}
          </div>

          {/* Pending or Error States */}
          {isPending ? <PageLoading label={t("audit.title")} /> : null}
          {isError ? (
            <PageError
              label={t("audit.title")}
              error={error}
              onRetry={() => void refetch()}
            />
          ) : null}

          {/* Content */}
          {data ? (
            <>
              {/* Integrity Status Banner */}
              <div
                className={`rounded-lg border p-4 shadow-sm transition-all ${
                  data.is_chain_intact
                    ? "border-success/30 bg-success/10 text-fg-body"
                    : "border-danger/30 bg-danger/10 text-fg-body"
                }`}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 rounded-full p-1 bg-surface shadow-xs">
                      {data.is_chain_intact ? (
                        <ShieldCheck className="size-5 text-success" />
                      ) : (
                        <ShieldAlert className="size-5 text-danger" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-block rounded px-1.5 py-0.5 font-mono text-[11px] font-bold ${
                            data.is_chain_intact
                              ? "bg-success text-white"
                              : "bg-danger text-white"
                          }`}
                        >
                          {data.is_chain_intact ? "[VERIFIED]" : "[FAILED]"}
                        </span>
                        <h2 className="text-sm font-semibold text-fg-header">
                          {data.is_chain_intact
                            ? t("audit.chainIntact")
                            : t("audit.chainBroken")}
                        </h2>
                      </div>
                      <p className="mt-0.5 text-xs text-fg-muted">
                        {t("audit.verifiedCount", {
                          verified: data.verified_records,
                          total: data.total_records,
                        })}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    <span className="font-mono text-xs text-fg-muted">Algorithm:</span>
                    <span className="inline-flex items-center rounded border border-line bg-surface px-2 py-0.5 font-mono text-xs text-fg-body">
                      SHA-256 HMAC-chained
                    </span>
                  </div>
                </div>
              </div>

              {/* Filter and Count Bar */}
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="relative w-full max-w-sm">
                  <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-fg-muted" />
                  <input
                    type="text"
                    value={filterQuery}
                    onChange={(e) => setFilterQuery(e.target.value)}
                    placeholder="Filter audit records by action or hash..."
                    className="w-full rounded-md border border-line bg-surface py-1.5 pl-9 pr-3 text-xs text-fg-body shadow-xs placeholder:text-fg-subtle focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  />
                </div>
                <div className="text-xs text-fg-muted">
                  Showing {filteredEvents.length} of {data.events.length} records
                </div>
              </div>

              {/* Audit Ledger Table */}
              <div className="overflow-hidden rounded-lg border border-line bg-surface shadow-xs">
                <div className="relative max-h-[34rem] overflow-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="sticky top-0 z-10 border-b border-line bg-surface-muted text-xs uppercase tracking-wider text-fg-muted">
                      <tr>
                        <th className="px-4 py-3 font-semibold">
                          {t("audit.headers.timestamp")}
                        </th>
                        <th className="px-4 py-3 font-semibold">
                          {t("audit.headers.action")}
                        </th>
                        <th className="px-4 py-3 font-semibold">
                          {t("audit.headers.status")}
                        </th>
                        <th className="px-4 py-3 font-semibold">
                          {t("audit.headers.detail")}
                        </th>
                        <th className="px-4 py-3 text-right font-semibold">
                          {t("audit.headers.proof")}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line-subtle">
                      {filteredEvents.length === 0 ? (
                        <tr>
                          <td
                            colSpan={5}
                            className="px-4 py-8 text-center text-sm text-fg-subtle"
                          >
                            {t("audit.empty")}
                          </td>
                        </tr>
                      ) : (
                        filteredEvents.map((event) => (
                          <tr
                            key={event.id}
                            className="transition-colors hover:bg-surface-hover/60"
                          >
                            {/* Timestamp */}
                            <td className="whitespace-nowrap px-4 py-3 text-xs text-fg-muted">
                              {event.created_at
                                ? format.timestamp(event.created_at)
                                : "N/A"}
                            </td>

                            {/* Action */}
                            <td className="whitespace-nowrap px-4 py-3">
                              <span className="inline-flex items-center rounded-md border border-line-subtle bg-surface px-2 py-0.5 text-xs font-medium text-fg-body">
                                {getActionLabel(event.action)}
                              </span>
                            </td>

                            {/* Status */}
                            <td className="whitespace-nowrap px-4 py-3 text-xs">
                              {event.success === null ? (
                                <span className="inline-flex items-center gap-1 font-mono text-fg-muted">
                                  <CircleHelp className="size-3.5" />
                                  {t("audit.status.unknown")}
                                </span>
                              ) : event.success === false ? (
                                <span className="inline-flex items-center gap-1 font-mono text-danger">
                                  <CircleAlert className="size-3.5" />
                                  {t("audit.status.failed")}
                                </span>
                              ) : event.action === "quarantine" ? (
                                <span className="inline-flex items-center gap-1 font-mono text-amber-600">
                                  <ShieldAlert className="size-3.5" />
                                  {t("audit.status.quarantined")}
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 font-mono text-success">
                                  <CircleCheck className="size-3.5" />
                                  {t("audit.status.passed")}
                                </span>
                              )}
                            </td>

                            {/* Detail / Summary */}
                            <td className="max-w-md truncate px-4 py-3 text-xs text-fg-body">
                              {formatSummary(event.detail, event.action)}
                            </td>

                            {/* Cryptographic Proof */}
                            <td className="whitespace-nowrap px-4 py-3 text-right">
                              {event.current_hash ? (
                                <button
                                  type="button"
                                  onClick={() => setSelectedEvent(event)}
                                  className="inline-flex items-center gap-1.5 rounded border border-line bg-surface-muted px-2 py-1 font-mono text-[11px] text-fg-muted transition-colors hover:border-accent hover:bg-surface hover:text-accent focus:outline-none focus:ring-1 focus:ring-accent"
                                  title="Inspect SHA-256 cryptographic proof"
                                >
                                  <Hash className="size-3 text-fg-subtle" />
                                  <span>
                                    {event.current_hash.slice(0, 6)}...
                                    {event.current_hash.slice(-4)}
                                  </span>
                                  {event.is_verified === false ? (
                                    <span className="ml-1 rounded bg-danger/15 px-1 py-0.5 text-[9px] font-bold text-danger">
                                      [TAMPERED]
                                    </span>
                                  ) : (
                                    <span className="ml-1 rounded bg-success/15 px-1 py-0.5 text-[9px] font-bold text-success">
                                      [OK]
                                    </span>
                                  )}
                                </button>
                              ) : (
                                <span className="font-mono text-xs text-fg-subtle">
                                  Legacy Log
                                </span>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </section>

      {/* Cryptographic Proof Modal */}
      <Dialog
        open={selectedEvent !== null}
        onOpenChange={(open) => !open && setSelectedEvent(null)}
      >
        <DialogContent className="max-w-xl sm:max-w-2xl bg-surface border border-line">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-5 text-success" />
              <DialogTitle className="text-base font-bold text-fg-header">
                {t("audit.modal.title")}
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-fg-muted">
              {t("audit.modal.subtitle")}
            </DialogDescription>
          </DialogHeader>

          {selectedEvent ? (
            <div className="space-y-4 py-2">
              {/* Event Metadata */}
              <div className="grid grid-cols-2 gap-3 rounded-lg border border-line bg-surface-muted p-3 text-xs">
                <div>
                  <span className="font-medium text-fg-muted">
                    {t("audit.modal.recordId")}:
                  </span>
                  <p className="mt-0.5 font-mono text-[11px] text-fg-body break-all">
                    {selectedEvent.id}
                  </p>
                </div>
                <div>
                  <span className="font-medium text-fg-muted">
                    {t("audit.modal.timestamp")}:
                  </span>
                  <p className="mt-0.5 text-fg-body">
                    {selectedEvent.created_at
                      ? format.timestamp(selectedEvent.created_at)
                      : "N/A"}
                  </p>
                </div>
                <div>
                  <span className="font-medium text-fg-muted">
                    {t("audit.modal.action")}:
                  </span>
                  <p className="mt-0.5 font-medium text-fg-body">
                    {getActionLabel(selectedEvent.action)}
                  </p>
                </div>
                <div>
                  <span className="font-medium text-fg-muted">Status:</span>
                  <p
                    className={`mt-0.5 font-mono font-medium ${
                      selectedEvent.is_verified === false ? "text-danger" : "text-success"
                    }`}
                  >
                    {selectedEvent.is_verified === false
                      ? "[ALERT] Cryptographic Hash Mismatch: Unauthorized Modification Detected!"
                      : "[VERIFIED] Integrity Intact"}
                  </p>
                </div>
              </div>

              {/* Hash Linkage Details */}
              <div className="space-y-3">
                {/* Previous Hash */}
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-fg-header flex items-center gap-1.5">
                      <LinkIcon className="size-3.5 text-fg-muted" />
                      {t("audit.modal.prevHash")}
                    </span>
                    {selectedEvent.prev_hash ? (
                      <button
                        type="button"
                        onClick={() =>
                          copyToClipboard(selectedEvent.prev_hash || "", "prev")
                        }
                        className="inline-flex items-center gap-1 text-[11px] text-fg-muted hover:text-fg-header"
                      >
                        {copiedField === "prev" ? (
                          <>
                            <Check className="size-3 text-success" />
                            <span>Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="size-3" />
                            <span>Copy</span>
                          </>
                        )}
                      </button>
                    ) : null}
                  </div>
                  <div className="mt-1 rounded border border-line bg-surface-muted p-2 font-mono text-[11px] text-fg-muted break-all select-all">
                    {selectedEvent.prev_hash ||
                      "0000000000000000000000000000000000000000000000000000000000000000 (Genesis)"}
                  </div>
                </div>

                {/* Mathematical Chaining Formula */}
                <div className="rounded-md border border-line/60 bg-surface px-3 py-2 text-xs">
                  <span className="font-mono text-[11px] font-semibold text-fg-header">
                    {t("audit.modal.formula")}:
                  </span>
                  <p className="mt-0.5 font-mono text-[10px] text-fg-muted break-all">
                    {t("audit.modal.formulaDesc")}
                  </p>
                </div>

                {/* Current Hash */}
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-fg-header flex items-center gap-1.5">
                      <Hash className="size-3.5 text-accent" />
                      {t("audit.modal.currentHash")}
                    </span>
                    {selectedEvent.current_hash ? (
                      <button
                        type="button"
                        onClick={() =>
                          copyToClipboard(selectedEvent.current_hash || "", "current")
                        }
                        className="inline-flex items-center gap-1 text-[11px] text-fg-muted hover:text-fg-header"
                      >
                        {copiedField === "current" ? (
                          <>
                            <Check className="size-3 text-success" />
                            <span>Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="size-3" />
                            <span>Copy</span>
                          </>
                        )}
                      </button>
                    ) : null}
                  </div>
                  <div className="mt-1 rounded border border-accent/40 bg-accent/5 p-2 font-mono text-[11px] font-medium text-accent break-all select-all">
                    {selectedEvent.current_hash || "N/A"}
                  </div>
                </div>
              </div>

              {/* Explanation Note */}
              <div className="rounded border border-line-subtle bg-surface-muted/60 p-3 text-xs text-fg-muted leading-relaxed">
                {t("audit.modal.intactMessage")}
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <button
              type="button"
              onClick={() => setSelectedEvent(null)}
              className="rounded-md border border-line bg-surface px-4 py-2 text-xs font-medium text-fg-body hover:bg-surface-hover hover:text-fg-header focus:outline-none focus:ring-2 focus:ring-accent"
            >
              {t("audit.modal.close")}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
