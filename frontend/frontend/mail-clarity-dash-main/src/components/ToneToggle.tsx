import { useTranslation } from "react-i18next";

import type { Tone } from "../types/email";

type ToneToggleProps = {
  tone: Tone;
  onToneChange: (tone: Tone) => void;
  disabled?: boolean;
};

const TONES: Tone[] = ["professional", "casual"];

export default function ToneToggle({ tone, onToneChange, disabled = false }: ToneToggleProps) {
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
          onClick={() => onToneChange(option)}
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
