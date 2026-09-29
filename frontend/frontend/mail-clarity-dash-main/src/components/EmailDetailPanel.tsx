import { useTranslation } from "react-i18next";

import { useFormat } from "../lib/useFormat";
import type { Email, Tone } from "../types/email";
import AISummaryCard from "./AISummaryCard";
import EmailBody from "./EmailBody";
import ActionItemsList from "./ActionItemsList";
import ThreadContextToggle from "./ThreadContextToggle";
import DraftReplyEditor from "./DraftReplyEditor";
import SourcesChips from "./SourcesChips";
import RefineInput from "./RefineInput";
import DraftActionsBar from "./DraftActionsBar";
import PriorityBadge from "./PriorityBadge";

type EmailDetailPanelProps = {
  email: Email | null;
  draft: string;
  tone: Tone;
  onDraftChange: (draft: string) => void;
  onToneChange: (emailId: string, tone: Tone) => void;
  onRegenerate: (emailId: string) => void;
  onRefine: (emailId: string, instruction: string) => void;
  onApproveSend: (emailId: string) => void;
  isRegenerating?: boolean;
  isRefining?: boolean;
  isSending?: boolean;
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
}: EmailDetailPanelProps) {
  const { t } = useTranslation();
  const format = useFormat();
  if (!email) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-sm text-fg-subtle">
        {t("detail.empty")}
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-line bg-surface px-6 py-4">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-base font-semibold text-fg">{email.subject}</h1>
          <PriorityBadge priority={email.priority} />
        </div>
        <p className="mt-0.5 text-sm text-fg-muted">
          {email.sender} &middot; {format.timestamp(email.timestamp)}
        </p>
      </header>

      <div className="space-y-4 p-6">
        <EmailBody key={email.id} email={email} />

        <AISummaryCard summary={email.aiSummary} />
        <ActionItemsList items={email.actionItems} />
        <ThreadContextToggle messages={email.threadContext} />

        <section className="space-y-4 rounded-lg border border-line bg-surface p-4">
          <DraftReplyEditor
            email={email}
            draft={draft}
            tone={tone}
            onDraftChange={onDraftChange}
            onToneChange={onToneChange}
            // A tone change regenerates the draft, so it is blocked mid-send like the rest.
            disabled={isRegenerating || isRefining || isSending}
          />

          <SourcesChips sources={email.sources} draft={draft} />

          <RefineInput
            emailId={email.id}
            onRefine={onRefine}
            disabled={isRefining || isRegenerating || isSending}
          />

          <div className="flex items-center justify-between gap-3 border-t border-line-subtle pt-4">
            <p className="text-xs text-fg-subtle">
              {email.sentAt
                ? t("detail.sentAt", { when: format.timestamp(email.sentAt) })
                : t("detail.notSentYet")}
            </p>
            <DraftActionsBar
              emailId={email.id}
              onRegenerate={onRegenerate}
              onApproveSend={onApproveSend}
              isRegenerating={isRegenerating}
              isRefining={isRefining}
              isSending={isSending}
              isSent={Boolean(email.sentAt)}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
