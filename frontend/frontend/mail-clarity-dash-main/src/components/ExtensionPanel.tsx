import { useTranslation } from "react-i18next";

import type { Email, Tone } from "../types/email";
import { useFormat } from "../lib/useFormat";
import AISummaryCard from "./AISummaryCard";
import ActionItemsList from "./ActionItemsList";
import ThreadContextToggle from "./ThreadContextToggle";
import DraftReplyEditor from "./DraftReplyEditor";
import SourcesChips from "./SourcesChips";
import RefineInput from "./RefineInput";
import DraftActionsBar from "./DraftActionsBar";
import DraftStatus, { type DraftStatusProps } from "./DraftStatus";

type ExtensionPanelProps = {
  email: Email;
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

/**
 * Condensed, fixed-width Chrome side panel. Same components as the dashboard —
 * only width and spacing differ.
 */
export default function ExtensionPanel({
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
}: ExtensionPanelProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const isDraftBusy = isRegenerating || isRefining || isSending || status.isGenerating;
  return (
    <div className="flex h-full w-[390px] flex-col border border-line bg-surface-muted">
      <header className="flex items-center justify-between border-b border-line bg-surface px-3 py-2">
        <span className="text-sm font-semibold text-fg">{t("app.name")}</span>
        <span className="text-xs text-fg-subtle">{t("extension.panel")}</span>
      </header>

      <div className="relative flex-1 space-y-3 overflow-y-auto p-3">
        <div>
          <p className="truncate text-sm font-medium text-fg">{email.subject}</p>
          <p className="text-xs text-fg-muted">
            {email.sender} &middot; {format.timestamp(email.timestamp)}
          </p>
        </div>

        <AISummaryCard summary={email.aiSummary} />
        <ActionItemsList items={email.actionItems} />
        <ThreadContextToggle messages={email.threadContext} defaultOpen={false} />

        <div className="space-y-3 rounded-lg border border-line bg-surface p-3">
          <DraftReplyEditor
            email={email}
            draft={draft}
            tone={tone}
            rows={6}
            onDraftChange={onDraftChange}
            onToneChange={onToneChange}
            disabled={isDraftBusy}
          />
          <SourcesChips sources={email.sources} draft={draft} />
          <RefineInput emailId={email.id} onRefine={onRefine} disabled={isDraftBusy} />
          <DraftStatus {...status} />
        </div>
      </div>

      <footer className="border-t border-line bg-surface p-3">
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
      </footer>
    </div>
  );
}
