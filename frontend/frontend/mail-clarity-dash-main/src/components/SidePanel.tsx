import { Eye } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { Email, Tone } from "../types/email";
import { StatusColours } from "../lib/preferences";
import { useFormat } from "../lib/useFormat";
import { usePreferences } from "../lib/usePreferences";
import DraftReplyEditor from "./DraftReplyEditor";
import SourcesChips from "./SourcesChips";
import RefineInput from "./RefineInput";
import DraftActionsBar from "./DraftActionsBar";
import DraftStatus, { type DraftStatusProps } from "./DraftStatus";
import PanelSummary from "./PanelSummary";
import QuarantineNotice from "./QuarantineNotice";

export type SidePanelProps = {
  email: Email;
  account?: string;
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
 * The Chrome extension's panel beside Gmail, also shown by the dashboard's /extension preview.
 * Gmail already shows the thread and the original, so the panel carries only what Gmail lacks:
 * the summary, the action items and the reply.
 */
export default function SidePanel({
  email,
  account,
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
}: SidePanelProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const isDraftBusy = isRegenerating || isRefining || isSending || status.isGenerating;
  const isMasked = email.masking === "complete";
  return (
    <div className="flex h-full w-full flex-col bg-surface-muted">
      <PanelHeader account={account} />

      <div className="relative flex-1 space-y-3 overflow-y-auto p-3">
        <div>
          <p className="line-clamp-2 text-sm font-semibold text-fg">{email.subject}</p>
          <p className="truncate text-xs text-fg-muted">
            {email.sender} &middot; {format.timestamp(email.timestamp)}
          </p>
        </div>

        {isMasked ? null : <QuarantineNotice isAbandoned={email.masking === "abandoned"} />}
        <PanelSummary summary={email.aiSummary} actionItems={email.actionItems} />

        <section
          aria-label={t("draft.title")}
          className="space-y-3 rounded-lg border border-line bg-surface p-3"
        >
          <DraftReplyEditor
            email={email}
            draft={draft}
            tone={tone}
            rows={9}
            onDraftChange={onDraftChange}
            onToneChange={onToneChange}
            disabled={isDraftBusy}
          />
          <RefineInput emailId={email.id} onRefine={onRefine} disabled={isDraftBusy} />
          {email.sources.length > 0 ? (
            <details className="group text-xs">
              <summary className="cursor-pointer font-medium text-fg-muted hover:text-fg-body">
                {t("extension.sources", { count: email.sources.length })}
              </summary>
              <div className="mt-2">
                <SourcesChips sources={email.sources} draft={draft} />
              </div>
            </details>
          ) : null}
          <DraftStatus {...status} />
        </section>
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

export function PanelHeader({ account }: { account?: string }) {
  const { t } = useTranslation();
  const { preferences, setColours } = usePreferences();
  const isFriendly = preferences.colours === StatusColours.Friendly;
  return (
    <header className="flex items-center gap-2 border-b border-line bg-surface px-3 py-2">
      <span className="text-sm font-semibold text-fg">{t("app.name")}</span>
      <span className="ml-auto truncate text-xs text-fg-subtle">{account}</span>
      <button
        type="button"
        aria-pressed={isFriendly}
        title={t("extension.friendlyColours")}
        aria-label={t("extension.friendlyColours")}
        onClick={() => setColours(isFriendly ? StatusColours.Standard : StatusColours.Friendly)}
        className={`rounded-md p-1 hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-brand ${isFriendly ? "text-brand" : "text-fg-subtle"}`}
      >
        <Eye aria-hidden className="size-4" />
      </button>
    </header>
  );
}
