import { useTranslation } from "react-i18next";

import type { Tone } from "../types/email";
import { segment } from "./variants";

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
          className={segment({ isPressed: tone === option })}
        >
          {t(`tone.${option}`)}
        </button>
      ))}
    </div>
  );
}
