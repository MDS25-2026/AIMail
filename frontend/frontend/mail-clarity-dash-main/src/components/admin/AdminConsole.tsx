import { Ban, FileWarning, ImageOff, LogOut, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  useAdminAudit,
  useAdminFlagged,
  useAdminOverview,
  useAdminSignOut,
  useSignedOutRecovery,
} from "../../lib/queries";
import type { AdminIdentity, Overview } from "../../types/admin";
import { PageError, PageLoading } from "../PageState";
import AuditTable from "./AuditTable";
import BarList from "./BarList";
import CompanyQuietHours from "./CompanyQuietHours";
import FlaggedTable from "./FlaggedTable";
import Panel from "./Panel";
import StatTile from "./StatTile";

const WINDOWS = [1, 7, 30] as const;
// A stat tile shows a dash, not a sentence, when there is nothing to show.
const NOT_MEASURED = "–";

export default function AdminConsole({ admin }: { admin: AdminIdentity }) {
  const { t } = useTranslation();
  const [days, setDays] = useState<number>(7);
  const [failuresOnly, setFailuresOnly] = useState(false);
  const overview = useAdminOverview(days, true);
  const flagged = useAdminFlagged(true);
  const audit = useAdminAudit(failuresOnly, true);
  const signOut = useAdminSignOut();
  useSignedOutRecovery([overview.error, flagged.error, audit.error]);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-fg">{t("admin.title")}</h1>
          <p className="mt-1 max-w-2xl text-sm text-fg-muted">{t("admin.subtitle")}</p>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-fg-muted">{t("admin.signedInAs", { email: admin.email })}</span>
          <button
            type="button"
            onClick={() => signOut.mutate()}
            className="inline-flex items-center gap-1 rounded-md border border-line-strong px-3 py-1.5 text-fg-body hover:bg-surface-muted"
          >
            <LogOut aria-hidden className="size-4" />
            {t("admin.signOut")}
          </button>
        </div>
      </header>

      <fieldset className="flex items-center gap-2 text-sm">
        <legend className="sr-only">{t("admin.window")}</legend>
        {WINDOWS.map((option) => (
          <button
            key={option}
            type="button"
            aria-pressed={days === option}
            onClick={() => setDays(option)}
            className={`rounded-md px-2.5 py-1 text-xs font-medium ${
              days === option
                ? "bg-brand text-on-brand"
                : "border border-line text-fg-muted hover:bg-surface-muted"
            }`}
          >
            {t("admin.days", { count: option })}
          </button>
        ))}
      </fieldset>

      {overview.isPending ? <PageLoading label={t("admin.loading")} /> : null}
      {overview.isError ? <PageError label={t("admin.loading")} error={overview.error} /> : null}
      {overview.data ? <OverviewPanels overview={overview.data} /> : null}

      <Panel title={t("admin.flagged")}>
        {flagged.isPending ? <PageLoading label={t("admin.flagged")} /> : null}
        {flagged.isError ? <PageError label={t("admin.flagged")} error={flagged.error} /> : null}
        {flagged.data ? <FlaggedTable drafts={flagged.data} /> : null}
      </Panel>

      <Panel title={t("admin.activity")}>
        <label className="mb-3 inline-flex items-center gap-2 text-sm text-fg-body">
          <input
            type="checkbox"
            checked={failuresOnly}
            onChange={(event) => setFailuresOnly(event.target.checked)}
          />
          {t("admin.failuresOnly")}
        </label>
        {audit.isPending ? <PageLoading label={t("admin.activity")} /> : null}
        {audit.isError ? <PageError label={t("admin.activity")} error={audit.error} /> : null}
        {audit.data ? <AuditTable events={audit.data} /> : null}
      </Panel>

      <Panel title={t("admin.quietHours")}>
        <CompanyQuietHours />
      </Panel>
    </div>
  );
}

function OverviewPanels({ overview }: { overview: Overview }) {
  const { t } = useTranslation();
  const { mailbox, privacy, models } = overview;
  // Both percentiles come from the same list: either both are measured or neither is.
  const latency =
    models.model_ms_p50 === null || models.model_ms_p95 === null
      ? NOT_MEASURED
      : t("admin.latencyValue", { p50: models.model_ms_p50, p95: models.model_ms_p95 });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title={t("admin.mailbox")}>
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <StatTile label={t("admin.total")} value={mailbox.total} />
          <StatTile label={t("admin.generated")} value={mailbox.generated} />
          <StatTile label={t("admin.awaitingReview")} value={mailbox.awaiting_review} />
          <StatTile label={t("admin.sentCount")} value={mailbox.sent} />
          <StatTile label={t("admin.unread")} value={mailbox.unread} />
          <StatTile
            label={t("admin.maskingPending")}
            value={mailbox.masking_pending}
            icon={ShieldAlert}
            isAlert={mailbox.masking_pending > 0}
          />
          <StatTile
            label={t("admin.maskingAbandoned")}
            value={mailbox.masking_abandoned}
            icon={ShieldAlert}
            isAlert={mailbox.masking_abandoned > 0}
          />
        </dl>
      </Panel>

      <Panel title={t("admin.privacy")}>
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <StatTile
            label={t("admin.quarantined")}
            value={privacy.quarantined}
            icon={ShieldAlert}
            isAlert={privacy.quarantined > 0}
          />
          <StatTile label={t("admin.released")} value={privacy.released} />
          <StatTile
            label={t("admin.degradedBefore")}
            value={privacy.degraded_before_fix}
            icon={Ban}
            isAlert={privacy.degraded_before_fix > 0}
          />
          <StatTile
            label={t("admin.attachmentDropped")}
            value={privacy.attachment_text_dropped}
            icon={FileWarning}
            isAlert={privacy.attachment_text_dropped > 0}
          />
          <StatTile
            label={t("admin.pagesWithheld")}
            value={privacy.pages_withheld}
            icon={ImageOff}
          />
          <StatTile
            label={t("admin.attachmentFailures")}
            value={privacy.attachment_failures}
            icon={FileWarning}
            isAlert={privacy.attachment_failures > 0}
          />
        </dl>
      </Panel>

      <Panel title={t("admin.reviewReasons")}>
        <BarList items={overview.review_reasons} label={t("admin.reviewReasons")} />
      </Panel>

      <Panel title={t("admin.models")}>
        <dl className="mb-4 grid grid-cols-2 gap-2">
          <StatTile label={t("admin.draftsTracked")} value={models.drafts} />
          <StatTile label={t("admin.attempts")} value={models.attempts} />
          <StatTile label={t("admin.fallback")} value={models.drafts_using_fallback} />
          <StatTile label={t("admin.latency")} value={latency} />
        </dl>
        <h3 className="mb-2 text-xs font-medium text-fg-muted">{t("admin.outcomes")}</h3>
        <BarList items={models.outcomes} label={t("admin.outcomes")} />
      </Panel>
    </div>
  );
}
