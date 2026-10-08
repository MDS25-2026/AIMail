import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { splitAround } from "../lib/conversations";
import { detailValues } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { DraftAvailability, draftAvailability } from "../lib/draftAvailability";
import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import { useFormat } from "../lib/useFormat";
import { AuthStatus, type Email } from "../types/email";
import ActionItemsList from "./ActionItemsList";
import AISummaryCard from "./AISummaryCard";
import ConversationMessages from "./ConversationMessages";
import DetailsToggle from "./DetailsToggle";
import DraftActionsBar from "./DraftActionsBar";
import DraftGate from "./DraftGate";
import DraftReplyEditor from "./DraftReplyEditor";
import DraftStatus from "./DraftStatus";
import EmailBody from "./EmailBody";
import HiddenDetailChips from "./HiddenDetailChips";
import MissingDetailsNotice from "./MissingDetailsNotice";
import PriorityBadge from "./PriorityBadge";
import PrivacyReceipt from "./PrivacyReceipt";
import RefineInput from "./RefineInput";
import SourcesChips from "./SourcesChips";
import UseAsExampleButton from "./UseAsExampleButton";
import WithDetails from "./WithDetails";

type EmailDetailPanelProps = { email: Email | null; workflow: DraftWorkflow };

export default function EmailDetailPanel({ email, workflow }: EmailDetailPanelProps) {
  const { t } = useTranslation();
  if (!email) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-sm text-fg-subtle">
        {t("detail.empty")}
      </div>
    );
  }

  const availability = draftAvailability(email);
  // Quarantined (#109): nothing to read or draft from until the listener can mask the content.
  if (availability === DraftAvailability.Quarantined) {
    return (
      <div className="relative h-full overflow-y-auto">
        <DetailHeader email={email} />
        <div className="p-6">
          <DraftGate email={email} availability={availability}>
            {null}
          </DraftGate>
        </div>
      </div>
    );
  }

  const conversation = splitAround(email.threadContext, email.timestamp);
  return (
    <DetailsContext.Provider value={detailValues(email.details)}>
      <div className="relative h-full overflow-y-auto">
        <DetailHeader email={email} />
        <div className="space-y-4 p-6">
          <MissingDetailsNotice email={email} draft={workflow.draft} />
          <ConversationMessages messages={conversation.earlier} />
          <EmailBody key={email.id} email={email} />
          <ConversationMessages messages={conversation.later} />
          <AISummaryCard summary={email.aiSummary} />
          <ActionItemsList items={email.actionItems} />
          <DraftGate email={email} availability={availability}>
            <DraftSection email={email} workflow={workflow} />
          </DraftGate>
        </div>
      </div>
    </DetailsContext.Provider>
  );
}

function DetailHeader({ email }: { email: Email }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <header className="border-b border-line bg-surface px-6 py-4">
      <div className="flex items-start justify-between gap-3">
        <h1 className="text-base font-semibold text-fg">
          <WithDetails text={email.subject} />
        </h1>
        <div className="flex shrink-0 items-center gap-2">
          {email.authStatus === AuthStatus.SpoofDetected ? (
            <span className="flex items-center gap-1 rounded bg-danger-soft px-2 py-0.5 text-xs font-semibold text-danger">
              <ShieldAlert aria-hidden className="size-3.5" />
              {t("security.spoofBadge")}
            </span>
          ) : null}
          <PrivacyReceipt email={email} />
          {email.details?.length ? <DetailsToggle /> : null}
          <PriorityBadge priority={email.priority} />
        </div>
      </div>
      <p className="mt-0.5 text-sm text-fg-muted">
        {t("detail.fromAt", { sender: email.sender, when: format.timestamp(email.timestamp) })}
      </p>
    </header>
  );
}

function DraftSection({ email, workflow }: { email: Email; workflow: DraftWorkflow }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <section className="space-y-4 rounded-lg border border-line bg-surface p-4">
      <DraftReplyEditor email={email} workflow={workflow} />
      <HiddenDetailChips
        key={`hidden-${email.id}`}
        draft={workflow.draft}
        values={detailValues(email.details)}
        onDraftChange={workflow.setDraft}
        disabled={workflow.isDraftLocked}
      />
      <SourcesChips key={email.id} sources={email.sources} draft={workflow.draft} />
      <RefineInput
        onRefine={workflow.refine}
        disabled={workflow.isDraftLocked}
        isRefining={workflow.isRefining}
      />
      <DraftStatus {...workflow.status} />
      <div className="flex items-center justify-between gap-3 border-t border-line-subtle pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs text-fg-subtle">
            {email.sentAt
              ? t("detail.sentAt", { when: format.timestamp(email.sentAt) })
              : t("detail.notSentYet")}
          </p>
          {email.sentAt ? <UseAsExampleButton key={email.id} emailId={email.id} /> : null}
        </div>
        <DraftActionsBar workflow={workflow} isSent={Boolean(email.sentAt)} />
      </div>
    </section>
  );
}
