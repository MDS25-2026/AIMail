import type { Email, Tone } from "../types/email";
import { formatTimestamp } from "../lib/formatTimestamp";
import OriginalEmailToggle from "./extension/OriginalEmailToggle";
import AISummaryCard from "./extension/AISummaryCard";
import ActionItemsList from "./extension/ActionItemsList";
import ThreadContextToggle from "./extension/ThreadContextToggle";
import DraftReplyEditor from "./extension/DraftReplyEditor";
import SourcesChips from "./extension/SourcesChips";
import RefineInput from "./extension/RefineInput";
import DraftActionsBar from "./extension/DraftActionsBar";
import PriorityBadge from "./extension/PriorityBadge";

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
}: EmailDetailPanelProps) {
  if (!email) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-sm text-slate-400">
        Select an email to see the AI draft
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-base font-semibold text-slate-900">{email.subject}</h1>
          <PriorityBadge priority={email.priority} />
        </div>
        <p className="mt-0.5 text-sm text-slate-500">
          {email.sender} &middot; {formatTimestamp(email.timestamp)}
        </p>
      </header>

      <div className="space-y-4 p-6">
        <OriginalEmailToggle
          sender={email.sender}
          subject={email.subject}
          body={email.originalBody}
        />
        <AISummaryCard summary={email.aiSummary} />
        <ActionItemsList items={email.actionItems} />
        <ThreadContextToggle messages={email.threadContext} />

        <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
          <DraftReplyEditor
            email={email}
            draft={draft}
            tone={tone}
            onDraftChange={onDraftChange}
            onToneChange={onToneChange}
            disabled={isRegenerating || isRefining}
          />

          <SourcesChips sources={email.sources} />

          <RefineInput emailId={email.id} onRefine={onRefine} disabled={isRefining} />

          <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
            <p className="text-xs text-slate-400">Nothing is sent until you approve this draft.</p>
            <DraftActionsBar
              emailId={email.id}
              onRegenerate={onRegenerate}
              onApproveSend={onApproveSend}
              isRegenerating={isRegenerating}
            />
          </div>
        </section>
      </div>
    </div>
  );
}
