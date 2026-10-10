import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import type { Email } from "../types/email";
import CriticConfidenceBadge from "./CriticConfidenceBadge";
import DraftDiff from "./DraftDiff";
import PiiMaskedBadge from "./PiiMaskedBadge";
import ToneToggle from "./ToneToggle";
import { segment } from "./variants";

type DraftReplyEditorProps = { email: Email; workflow: DraftWorkflow; rows?: number };

export default function DraftReplyEditor({ email, workflow, rows = 10 }: DraftReplyEditorProps) {
  const { t } = useTranslation();
  // Remembers which email Changes was opened on, so opening another email starts on Draft.
  const [changesFor, setChangesFor] = useState<string | null>(null);
  const isShowingChanges = changesFor === email.id;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-fg">{t("draft.title")}</h3>
        {/* A tone change regenerates the draft, so it is blocked mid-send like the rest. */}
        <ToneToggle
          tone={workflow.tone}
          onToneChange={workflow.setTone}
          disabled={workflow.isDraftLocked}
        />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <CriticConfidenceBadge value={email.criticConfidence} />
        <PiiMaskedBadge masked={email.piiMasked} />
        <div
          role="group"
          aria-label={t("draftDiff.view")}
          className="ml-auto inline-flex rounded-md border border-line bg-surface-muted p-0.5"
        >
          {[false, true].map((changes) => (
            <button
              key={String(changes)}
              type="button"
              aria-pressed={isShowingChanges === changes}
              onClick={() => setChangesFor(changes ? email.id : null)}
              className={segment({ isPressed: isShowingChanges === changes })}
            >
              {t(changes ? "draftDiff.changes" : "draftDiff.draft")}
            </button>
          ))}
        </div>
      </div>

      {isShowingChanges ? (
        <DraftDiff comparison={workflow.comparison} rows={rows} />
      ) : (
        <textarea
          value={workflow.draft}
          rows={rows}
          disabled={workflow.isDraftLocked}
          aria-label={t("draft.title")}
          onChange={(event) => workflow.setDraft(event.target.value)}
          className="mt-2 w-full resize-y rounded-md border border-line-strong p-3 text-sm leading-relaxed text-fg disabled:bg-surface-muted disabled:text-fg-subtle"
        />
      )}
    </div>
  );
}
