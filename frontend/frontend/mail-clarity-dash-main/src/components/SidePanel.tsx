import { Contrast } from "lucide-react";
import { useTranslation } from "react-i18next";

import { detailValues } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { DraftAvailability, draftAvailability } from "../lib/draftAvailability";
import { StatusColours } from "../lib/preferences";
import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import { useFormat } from "../lib/useFormat";
import { usePreferences } from "../lib/usePreferences";
import type { Email } from "../types/email";
import DetailsToggle from "./DetailsToggle";
import DraftActionsBar from "./DraftActionsBar";
import DraftGate from "./DraftGate";
import DraftReplyEditor from "./DraftReplyEditor";
import DraftStatus from "./DraftStatus";
import HiddenDetailChips from "./HiddenDetailChips";
import MissingDetailsNotice from "./MissingDetailsNotice";
import PanelSummary from "./PanelSummary";
import PrivacyReceipt from "./PrivacyReceipt";
import RefineInput from "./RefineInput";
import SourcesChips from "./SourcesChips";
import WithDetails from "./WithDetails";

export type SidePanelProps = { email: Email; workflow: DraftWorkflow; account?: string };

/**
 * The Chrome extension's panel beside Gmail, also shown by the dashboard's /extension preview.
 * Gmail already shows the thread and the original, so the panel carries only what Gmail lacks:
 * the summary, the action items and the reply. It gates the draft exactly as the inbox does.
 */
export default function SidePanel({ email, workflow, account }: SidePanelProps) {
  const availability = draftAvailability(email);
  const isQuarantined = availability === DraftAvailability.Quarantined;
  const isDraftShown = availability !== DraftAvailability.NeedsSenderCheck && !isQuarantined;
  return (
    <DetailsContext.Provider value={detailValues(email.details)}>
      <div className="flex h-full w-full flex-col bg-surface-muted">
        <PanelHeader account={account} hasDetails={Boolean(email.details?.length)} />

        <div className="relative flex-1 space-y-3 overflow-y-auto p-3">
          <PanelTitle email={email} />
          {isQuarantined ? null : (
            <>
              <MissingDetailsNotice email={email} draft={workflow.draft} />
              <PanelSummary summary={email.aiSummary} actionItems={email.actionItems} />
            </>
          )}
          <DraftGate email={email} availability={availability}>
            <PanelDraft email={email} workflow={workflow} />
          </DraftGate>
        </div>

        {isDraftShown ? (
          <footer className="border-t border-line bg-surface p-3">
            <DraftActionsBar workflow={workflow} isSent={Boolean(email.sentAt)} />
          </footer>
        ) : null}
      </div>
    </DetailsContext.Provider>
  );
}

function PanelTitle({ email }: { email: Email }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <div className="flex items-start gap-2">
      <div className="min-w-0 flex-1">
        <p className="line-clamp-2 text-sm font-semibold text-fg">
          <WithDetails text={email.subject} />
        </p>
        <p className="truncate text-xs text-fg-muted">
          {t("detail.fromAt", { sender: email.sender, when: format.timestamp(email.timestamp) })}
        </p>
      </div>
      <PrivacyReceipt email={email} />
    </div>
  );
}

function PanelDraft({ email, workflow }: { email: Email; workflow: DraftWorkflow }) {
  const { t } = useTranslation();
  return (
    <section
      aria-label={t("draft.title")}
      className="space-y-3 rounded-lg border border-line bg-surface p-3"
    >
      <DraftReplyEditor email={email} workflow={workflow} rows={9} />
      <HiddenDetailChips
        key={`hidden-${email.id}`}
        draft={workflow.draft}
        values={detailValues(email.details)}
        onDraftChange={workflow.setDraft}
        disabled={workflow.isBusy}
      />
      <RefineInput onRefine={workflow.refine} disabled={workflow.isBusy} />
      {email.sources.length > 0 ? (
        <details className="group text-xs">
          <summary className="cursor-pointer font-medium text-fg-muted hover:text-fg-body">
            {t("extension.sources", { count: email.sources.length })}
          </summary>
          <div className="mt-2">
            <SourcesChips sources={email.sources} draft={workflow.draft} />
          </div>
        </details>
      ) : null}
      <DraftStatus {...workflow.status} />
    </section>
  );
}

export function PanelHeader({
  account,
  hasDetails = false,
}: {
  account?: string;
  hasDetails?: boolean;
}) {
  const { t } = useTranslation();
  const { preferences, setColours } = usePreferences();
  const isFriendly = preferences.colours === StatusColours.Friendly;
  return (
    <header className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2">
      <span className="text-sm font-semibold text-fg">{t("app.name")}</span>
      <span className="ml-auto truncate text-xs text-fg-subtle">{account}</span>
      {hasDetails ? <DetailsToggle isCompact /> : null}
      <button
        type="button"
        aria-pressed={isFriendly}
        title={t("extension.friendlyColours")}
        aria-label={t("extension.friendlyColours")}
        onClick={() => setColours(isFriendly ? StatusColours.Standard : StatusColours.Friendly)}
        className={`rounded-md p-1 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-brand ${isFriendly ? "text-brand" : "text-fg-subtle"}`}
      >
        <Contrast aria-hidden className="size-4" />
      </button>
    </header>
  );
}
