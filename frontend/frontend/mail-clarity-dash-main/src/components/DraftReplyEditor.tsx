import { useTranslation } from "react-i18next";

import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import type { Email } from "../types/email";
import CriticConfidenceBadge from "./CriticConfidenceBadge";
import PiiMaskedBadge from "./PiiMaskedBadge";
import ToneToggle from "./ToneToggle";

type DraftReplyEditorProps = { email: Email; workflow: DraftWorkflow; rows?: number };

export default function DraftReplyEditor({ email, workflow, rows = 10 }: DraftReplyEditorProps) {
  const { t } = useTranslation();
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-fg">{t("draft.title")}</h3>
        {/* A tone change regenerates the draft, so it is blocked mid-send like the rest. */}
        <ToneToggle
          tone={workflow.tone}
          onToneChange={workflow.setTone}
          disabled={workflow.isBusy}
        />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <CriticConfidenceBadge value={email.criticConfidence} />
        <PiiMaskedBadge masked={email.piiMasked} />
      </div>

      <textarea
        value={workflow.draft}
        rows={rows}
        disabled={workflow.isBusy}
        aria-label={t("draft.title")}
        onChange={(event) => workflow.setDraft(event.target.value)}
        className="mt-2 w-full resize-y rounded-md border border-line-strong p-3 text-sm leading-relaxed text-fg disabled:bg-surface-muted disabled:text-fg-subtle"
      />
    </div>
  );
}
