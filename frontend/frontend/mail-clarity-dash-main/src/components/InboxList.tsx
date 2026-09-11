import type { Email, Priority } from "../types/email";
import EmailListItem from "./EmailListItem";

type FilterPriority = "all" | Priority;

type InboxListProps = {
  emails: Email[];
  selectedEmailId: string | null;
  onSelectEmail: (emailId: string) => void;
  filterPriority: FilterPriority;
  onFilterChange: (priority: FilterPriority) => void;
};

const EMPTY_MESSAGES: Record<Exclude<FilterPriority, "all">, string> = {
  high: "No urgent emails right now.",
  medium: "No medium-priority emails right now.",
  low: "No low-priority emails right now.",
};

export default function InboxList({
  emails,
  selectedEmailId,
  onSelectEmail,
  filterPriority,
  onFilterChange,
}: InboxListProps) {
  const filteredEmails =
    filterPriority === "all"
      ? emails
      : emails.filter((email) => email.priority === filterPriority);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">Inbox</h2>
          <p className="text-xs text-slate-500">{filteredEmails.length} messages</p>
        </div>
        <select
          value={filterPriority}
          onChange={(e) => onFilterChange(e.target.value as FilterPriority)}
          className="mt-0.5 rounded border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600 outline-none hover:border-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        >
          <option value="all">All Priorities</option>
          <option value="high">Urgent</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>
      <ul className="flex-1 divide-y divide-slate-100 overflow-y-auto">
        {filteredEmails.length === 0 ? (
          <li className="flex h-full items-center justify-center p-8 text-sm text-slate-400">
            {filterPriority === "all" ? "No emails yet." : EMPTY_MESSAGES[filterPriority]}
          </li>
        ) : (
          filteredEmails.map((email) => (
            <EmailListItem
              key={email.id}
              email={email}
              selected={email.id === selectedEmailId}
              onSelect={onSelectEmail}
            />
          ))
        )}
      </ul>
    </div>
  );
}
