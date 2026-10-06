import type { Tone } from "../types/email";

type ToneToggleProps = {
  emailId: string;
  tone: Tone;
  onToneChange: (emailId: string, tone: Tone) => void;
};

const TONES: Tone[] = ["professional", "casual"];

export default function ToneToggle({ emailId, tone, onToneChange }: ToneToggleProps) {
  return (
    <div className="inline-flex rounded-md border border-slate-200 bg-slate-50 p-0.5">
      {TONES.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={tone === option}
          onClick={() => onToneChange(emailId, option)}
          className={`rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
            tone === option
              ? "bg-white text-slate-900 shadow-sm"
              : "text-slate-500 hover:text-slate-700"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
