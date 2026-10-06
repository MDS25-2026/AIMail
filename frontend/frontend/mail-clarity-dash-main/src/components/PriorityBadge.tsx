import type { Priority } from "../types/email";

const STYLES: Record<Priority, string> = {
  high: "bg-slate-900 text-white",
  medium: "border border-slate-300 text-slate-700",
  low: "border border-slate-200 text-slate-400",
};

const LABELS: Record<Priority, string> = {
  high: "Urgent",
  medium: "Medium",
  low: "Low",
};

export default function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STYLES[priority]}`}
    >
      {LABELS[priority]}
    </span>
  );
}
