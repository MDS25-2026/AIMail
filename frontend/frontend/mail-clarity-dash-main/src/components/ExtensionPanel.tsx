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

type ExtensionPanelProps = {
  email: Email;
  draft: string;
  tone: Tone;
  onDraftChange: (draft: string) => void;
  onToneChange: (emailId: string, tone: Tone) => void;
  onRegenerate: (emailId: string) => void;
  onRefine: (emailId: string, instruction: string) => void;
  onApproveSend: (emailId: string) => void;
  isRegenerating?: boolean;
  isRefining?: boolean;
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
}: ExtensionPanelProps) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <div className="flex h-full w-[390px] flex-col border border-line bg-surface-muted">
      <header className="flex items-center justify-between border-b border-line bg-surface px-3 py-2">
        <span className="text-sm font-semibold text-fg">{t("app.name")}</span>
        <span className="text-xs text-fg-subtle">{t("extension.panel")}</span>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
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
            disabled={isRegenerating || isRefining}
          />
          <SourcesChips sources={email.sources} draft={draft} />
          <RefineInput emailId={email.id} onRefine={onRefine} disabled={isRefining} />
        </div>
      </div>

      <footer className="border-t border-line bg-surface p-3">
        <DraftActionsBar
          emailId={email.id}
          onRegenerate={onRegenerate}
          onApproveSend={onApproveSend}
          isRegenerating={isRegenerating}
        />
      </footer>
    </div>
  );
}
