import { useState } from "react";

import type { ThreadMessage } from "./types";

type ThreadContextToggleProps = {
  messages: ThreadMessage[];
  defaultOpen?: boolean;
};

export default function ThreadContextToggle({
  messages,
  defaultOpen = true,
}: ThreadContextToggleProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (messages.length === 0) return null;

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between rounded-lg px-4 py-3 text-left transition-colors hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Thread context ({messages.length})
        </span>
        <span aria-hidden className="text-xs text-slate-500">
          {open ? "Hide" : "Show"}
        </span>
      </button>

      {open && (
        <ul className="space-y-2 border-t border-slate-100 px-4 py-3">
          {messages.map((message, index) => (
            <li key={index} className="text-xs text-slate-500">
              <span className="font-medium text-slate-700">{message.sender}: </span>
              {message.snippet}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
