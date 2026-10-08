import { useTranslation } from "react-i18next";

import type { Tone } from "../types/email";

type ToneToggleProps = {
  emailId: string;
  tone: Tone;
  onToneChange: (emailId: string, tone: Tone) => void;
  /** A tone change regenerates the draft, so it is blocked whenever the draft may not change. */
  disabled?: boolean;
};

const TONES: Tone[] = ["professional", "casual"];

export default function ToneToggle({
  emailId,
  tone,
  onToneChange,
  disabled = false,
}: ToneToggleProps) {
  const { t } = useTranslation();
  return (
    <div
      role="group"
      aria-label={t("tone.label")}
      className="inline-flex rounded-md border border-line bg-surface-muted p-0.5"
    >
      {TONES.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={tone === option}
          disabled={disabled}
          onClick={() => onToneChange(emailId, option)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            tone === option
              ? "bg-surface text-fg shadow-sm"
              : "text-fg-muted hover:text-fg-body disabled:hover:text-fg-muted"
          } disabled:cursor-not-allowed`}
        >
          {t(`tone.${option}`)}
        </button>
      ))}
    </div>
  );
}
