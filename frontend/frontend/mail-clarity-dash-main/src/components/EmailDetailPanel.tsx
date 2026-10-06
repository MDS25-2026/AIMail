import DOMPurify from "dompurify";

import type { Email, Tone } from "../types/email";
import { formatTimestamp } from "../lib/formatTimestamp";
import AISummaryCard from "./AISummaryCard";
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
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">Email</h2>
          {/^\s*<[a-z!]/i.test(email.body) ? (
            <div
              className="max-w-none overflow-x-auto text-sm text-slate-700 [&_a]:text-blue-600 [&_a]:underline [&_img]:max-w-full"
              // Email HTML is untrusted — sanitize to strip scripts/handlers before rendering.
              dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(email.body) }}
            />
          ) : (
            <p className="whitespace-pre-wrap text-sm text-slate-700">{email.body}</p>
          )}
        </section>

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
            // A tone change regenerates the draft, so it is blocked mid-send like the rest.
            disabled={isRegenerating || isRefining || isSending}
          />

          <SourcesChips sources={email.sources} />

          <RefineInput emailId={email.id} onRefine={onRefine} disabled={isRefining || isRegenerating || isSending} />

          <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
            <p className="text-xs text-slate-400">
              {email.sentAt
                ? `Sent ${formatTimestamp(email.sentAt)}`
                : "Nothing is sent until you approve this draft."}
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
