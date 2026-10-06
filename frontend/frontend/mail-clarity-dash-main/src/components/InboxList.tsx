import type { Email } from "../types/email";
import EmailListItem from "./EmailListItem";

type InboxListProps = {
  emails: Email[];
  selectedEmailId: string | null;
  onSelectEmail: (emailId: string) => void;
};

export default function InboxList({ emails, selectedEmailId, onSelectEmail }: InboxListProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-800">Inbox</h2>
        <p className="text-xs text-slate-500">{emails.length} messages</p>
      </div>
      <ul className="flex-1 divide-y divide-slate-100 overflow-y-auto">
        {emails.map((email) => (
          <EmailListItem
            key={email.id}
            email={email}
            selected={email.id === selectedEmailId}
            onSelect={onSelectEmail}
          />
        ))}
      </ul>
    </div>
  );
}
