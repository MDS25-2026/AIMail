import type { Email } from "../types/email";
import { formatTimestamp } from "../lib/formatTimestamp";
import PriorityBadge from "./PriorityBadge";

type EmailListItemProps = {
  email: Email;
  selected: boolean;
  onSelect: (emailId: string) => void;
};

export default function EmailListItem({ email, selected, onSelect }: EmailListItemProps) {
  return (
    <li>
      <button
        type="button"
        aria-current={selected}
        onClick={() => onSelect(email.id)}
        className={`w-full border-l-2 px-4 py-3 text-left transition-colors ${
          selected ? "border-blue-600 bg-blue-50" : "border-transparent hover:bg-slate-50"
        }`}
      >
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm font-semibold text-slate-800">{email.sender}</span>
          <span className="shrink-0 text-xs text-slate-400">
            {formatTimestamp(email.timestamp)}
          </span>
        </div>
        <div className="mt-0.5 truncate text-sm text-slate-700">{email.subject}</div>
        <p className="mt-0.5 line-clamp-2 text-xs text-slate-500">{email.preview}</p>
        <div className="mt-2">
          <PriorityBadge priority={email.priority} />
        </div>
      </button>
    </li>
  );
}
