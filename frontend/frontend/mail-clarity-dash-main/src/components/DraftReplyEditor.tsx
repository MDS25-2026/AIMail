import { useTranslation } from "react-i18next";

import type { Email, Tone } from "../types/email";
import CriticConfidenceBadge from "./CriticConfidenceBadge";
import PiiMaskedBadge from "./PiiMaskedBadge";
import ToneToggle from "./ToneToggle";

type DraftReplyEditorProps = {
  email: Email;
  draft: string;
  tone: Tone;
  onDraftChange: (draft: string) => void;
  onToneChange: (emailId: string, tone: Tone) => void;
  rows?: number;
  disabled?: boolean;
};

export default function DraftReplyEditor({
  email,
  draft,
  tone,
  onDraftChange,
  onToneChange,
  rows = 10,
  disabled = false,
}: DraftReplyEditorProps) {
  const { t } = useTranslation();
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-fg">{t("draft.title")}</h3>
        <ToneToggle emailId={email.id} tone={tone} onToneChange={onToneChange} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <CriticConfidenceBadge value={email.criticConfidence} />
        <PiiMaskedBadge masked={email.piiMasked} />
      </div>

      <textarea
        value={draft}
        rows={rows}
        disabled={disabled}
        aria-label={t("draft.title")}
        onChange={(event) => onDraftChange(event.target.value)}
        className="mt-2 w-full resize-y rounded-md border border-line-strong p-3 text-sm leading-relaxed text-fg disabled:bg-surface-muted disabled:text-fg-subtle"
      />
    </div>
  );
}
