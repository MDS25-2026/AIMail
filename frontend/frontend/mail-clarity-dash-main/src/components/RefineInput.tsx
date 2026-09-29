import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

type RefineInputProps = {
  emailId: string;
  onRefine: (emailId: string, instruction: string) => void;
  disabled?: boolean;
};

// Keys, not text: the suggestion is sent to the model in the reader's language.
const SUGGESTIONS = ["refine.suggestionDirect", "refine.suggestionDeadline"] as const;

export default function RefineInput({ emailId, onRefine, disabled = false }: RefineInputProps) {
  const { t } = useTranslation();
  const [instruction, setInstruction] = useState("");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = instruction.trim();
    if (!trimmed) return;
    onRefine(emailId, trimmed);
    setInstruction("");
  };

  return (
    <div>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={instruction}
          disabled={disabled}
          onChange={(event) => setInstruction(event.target.value)}
          placeholder={t("refine.placeholder")}
          aria-label={t("refine.placeholder")}
          className="flex-1 rounded-md border border-line-strong px-3 py-2 text-sm text-fg placeholder:text-fg-subtle disabled:bg-surface-muted"
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-md border border-line-strong bg-surface px-3 py-2 text-sm font-medium text-fg-body hover:bg-surface-muted disabled:cursor-not-allowed disabled:text-fg-subtle"
        >
          {disabled ? t("refine.pending") : t("refine.submit")}
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            disabled={disabled}
            onClick={() => onRefine(emailId, t(suggestion))}
            className="rounded-full border border-line bg-surface px-2.5 py-1 text-xs text-fg-body hover:bg-surface-muted disabled:cursor-not-allowed disabled:text-fg-subtle"
          >
            {t(suggestion)}
          </button>
        ))}
      </div>
    </div>
  );
}
