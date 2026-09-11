import { useState } from "react";

type OriginalEmailToggleProps = {
  sender: string;
  subject: string;
  body: string;
  defaultOpen?: boolean;
};

export default function OriginalEmailToggle({
  sender,
  subject,
  body,
  defaultOpen = false,
}: OriginalEmailToggleProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (!body) return null;

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between rounded-lg px-4 py-3 text-left transition-colors hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {open ? "Original email" : "Expand to read original email"}
        </span>
        <span aria-hidden className="text-xs text-slate-500">
          {open ? "Hide" : "Show"}
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 py-3">
          <p className="text-xs text-slate-500">
            From <span className="font-medium text-slate-700">{sender}</span>
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            Subject: <span className="font-medium text-slate-700">{subject}</span>
          </p>
          <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700">{body}</p>
        </div>
      )}
    </section>
  );
}
