import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { splitAround } from "../lib/conversations";
import { detailValues } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { useFormat } from "../lib/useFormat";
import { AuthStatus, type Email, type Tone } from "../types/email";
import AISummaryCard from "./AISummaryCard";
import EmailBody from "./EmailBody";
import QuarantineNotice from "./QuarantineNotice";
import SecurityNotice from "./SecurityNotice";
import ActionItemsList from "./ActionItemsList";
import ConversationMessages from "./ConversationMessages";
import DraftReplyEditor from "./DraftReplyEditor";
import SourcesChips from "./SourcesChips";
import RefineInput from "./RefineInput";
import DraftActionsBar from "./DraftActionsBar";
import DraftStatus, { type DraftStatusProps } from "./DraftStatus";
import PriorityBadge from "./PriorityBadge";
import DetailsToggle from "./DetailsToggle";
import MissingDetailsNotice from "./MissingDetailsNotice";
import WithDetails from "./WithDetails";
import UseAsExampleButton from "./UseAsExampleButton";

type EmailDetailPanelProps = {
  email: Email | null;
  draft: string;
  tone: Tone;
  onDraftChange: (draft: string) => void;
  onToneChange: (emailId: string, tone: Tone) => void;
  onRegenerate: (emailId: string) => void;
  onRefine: (emailId: string, instruction: string) => Promise<void>;
  onApproveSend: (emailId: string) => void;
  isRegenerating?: boolean;
  isRefining?: boolean;
  isSending?: boolean;
  status: DraftStatusProps;
};

export default function EmailDetailPanel({
  email,
  draft,
  tone,
  onDraftChange,
  onToneChange,
  onRegenerate,
  onRefine,
  onApproveSend,
  isRegenerating = false,
  isRefining = false,
  isSending = false,
  status,
}: EmailDetailPanelProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const isDraftBusy = isRegenerating || isRefining || isSending || status.isGenerating;
  if (!email) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-sm text-fg-subtle">
        {t("detail.empty")}
      </div>
    );
  }

  const conversation = splitAround(email.threadContext, email.timestamp);

  const header = (
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
          {email.details?.length ? <DetailsToggle /> : null}
          <PriorityBadge priority={email.priority} />
        </div>
      </div>
      <p className="mt-0.5 text-sm text-fg-muted">
        {email.sender} &middot; {format.timestamp(email.timestamp)}
      </p>
    </header>
  );

  // Quarantined (#109): nothing to read or draft from until the listener can mask the content.
  if (email.masking === "pending" || email.masking === "abandoned") {
    return (
      <div className="relative h-full overflow-y-auto">
        {header}
        <div className="p-6">
          <QuarantineNotice isAbandoned={email.masking === "abandoned"} />
        </div>
      </div>
    );
  }

  return (
    <DetailsContext.Provider value={detailValues(email.details)}>
      <div className="relative h-full overflow-y-auto">
        {header}

        <div className="space-y-4 p-6">
          <MissingDetailsNotice email={email} draft={draft} />
          <ConversationMessages messages={conversation.earlier} />
          <EmailBody key={email.id} email={email} />
          <ConversationMessages messages={conversation.later} />

          <AISummaryCard summary={email.aiSummary} />
          <ActionItemsList items={email.actionItems} />

          {email.authStatus === AuthStatus.SpoofDetected ? (
            <SecurityNotice emailId={email.id} />
          ) : (
            <section className="space-y-4 rounded-lg border border-line bg-surface p-4">
              <DraftReplyEditor
                email={email}
                draft={draft}
                tone={tone}
                onDraftChange={onDraftChange}
                onToneChange={onToneChange}
                // A tone change regenerates the draft, so it is blocked mid-send like the rest.
                disabled={isDraftBusy}
              />

              <SourcesChips key={email.id} sources={email.sources} draft={draft} />

              <RefineInput emailId={email.id} onRefine={onRefine} disabled={isDraftBusy} />

              <DraftStatus {...status} />

              <div className="flex items-center justify-between gap-3 border-t border-line-subtle pt-4">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-xs text-fg-subtle">
                    {email.sentAt
                      ? t("detail.sentAt", { when: format.timestamp(email.sentAt) })
                      : t("detail.notSentYet")}
                  </p>
                  {email.sentAt ? <UseAsExampleButton key={email.id} emailId={email.id} /> : null}
                </div>
                <DraftActionsBar
                  emailId={email.id}
                  onRegenerate={onRegenerate}
                  onApproveSend={onApproveSend}
                  isRegenerating={isRegenerating}
                  isRefining={isRefining}
                  isSending={isSending}
                  isSent={Boolean(email.sentAt)}
                  isGenerating={status.isGenerating}
                />
              </div>
            </section>
          )}
        </div>
      </div>
    </DetailsContext.Provider>
  );
}
