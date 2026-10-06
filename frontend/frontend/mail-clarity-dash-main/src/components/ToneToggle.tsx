import { useTranslation } from "react-i18next";

import type { Tone } from "../types/email";

type ToneToggleProps = {
  emailId: string;
  tone: Tone;
  onToneChange: (emailId: string, tone: Tone) => void;
};

const TONES: Tone[] = ["professional", "casual"];

export default function ToneToggle({ emailId, tone, onToneChange }: ToneToggleProps) {
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
          onClick={() => onToneChange(emailId, option)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            tone === option ? "bg-surface text-fg shadow-sm" : "text-fg-muted hover:text-fg-body"
          }`}
        >
          {t(`tone.${option}`)}
        </button>
      ))}
    </div>
  );
}
