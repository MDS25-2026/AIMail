import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../lib/utils";
import { button, field } from "./variants";

type RefineInputProps = {
  /** Rejects when the refine fails. */
  onRefine: (instruction: string) => Promise<void>;
  disabled?: boolean;
};

// Keys, not text: the suggestion is sent to the model in the reader's language.
const SUGGESTIONS = ["refine.suggestionDirect", "refine.suggestionDeadline"] as const;

export default function RefineInput({ onRefine, disabled = false }: RefineInputProps) {
  const { t } = useTranslation();
  const [instruction, setInstruction] = useState("");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = instruction.trim();
    if (!trimmed) return;
    // Cleared only once the refine lands: a failed one keeps the instruction for the retry.
    onRefine(trimmed).then(
      () => setInstruction(""),
      () => undefined,
    );
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
          className={cn(field(), "flex-1")}
        />
        <button type="submit" disabled={disabled} className={button({ size: "md" })}>
          {disabled ? t("refine.pending") : t("refine.submit")}
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            disabled={disabled}
            onClick={() => void onRefine(t(suggestion)).catch(() => undefined)}
            className="rounded-full border border-line bg-surface px-2.5 py-1 text-xs text-fg-body hover:bg-surface-muted disabled:cursor-not-allowed disabled:text-fg-subtle"
          >
            {t(suggestion)}
          </button>
        ))}
      </div>
    </div>
  );
}
