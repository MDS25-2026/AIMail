import { useState, type FormEvent } from "react";

type RefineInputProps = {
  emailId: string;
  onRefine: (emailId: string, instruction: string) => void;
  disabled?: boolean;
};

const SUGGESTIONS = ["Make it more direct", "Add a deadline"];

export default function RefineInput({ emailId, onRefine, disabled = false }: RefineInputProps) {
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
          placeholder="Ask AI to refine reply..."
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20 disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-400 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:text-slate-400"
        >
          {disabled ? "Refining…" : "Refine"}
        </button>
      </form>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            disabled={disabled}
            onClick={() => onRefine(emailId, suggestion)}
            className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:text-slate-400"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}
