import type { Email, Tone } from "../types/email";
import { formatTimestamp } from "../lib/formatTimestamp";
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
  return (
    <div className="flex h-full w-[390px] flex-col border border-slate-200 bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-3 py-2">
        <span className="text-sm font-semibold text-slate-900">iMail</span>
        <span className="text-xs text-slate-400">Extension panel</span>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        <div>
          <p className="truncate text-sm font-medium text-slate-800">{email.subject}</p>
          <p className="text-xs text-slate-500">
            {email.sender} &middot; {formatTimestamp(email.timestamp)}
          </p>
        </div>

        <AISummaryCard summary={email.aiSummary} />
        <ActionItemsList items={email.actionItems} />
        <ThreadContextToggle messages={email.threadContext} defaultOpen={false} />

        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-3">
          <DraftReplyEditor
            email={email}
            draft={draft}
            tone={tone}
            rows={6}
            onDraftChange={onDraftChange}
            onToneChange={onToneChange}
            disabled={isRegenerating || isRefining}
          />
          <SourcesChips sources={email.sources} />
          <RefineInput emailId={email.id} onRefine={onRefine} disabled={isRefining} />
        </div>
      </div>

      <footer className="border-t border-slate-200 bg-white p-3">
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
