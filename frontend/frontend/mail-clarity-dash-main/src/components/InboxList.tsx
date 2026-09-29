import { useTranslation } from "react-i18next";

import { inboxKeyHandler } from "../lib/inboxKeys";
import type { Email } from "../types/email";
import EmailListItem from "./EmailListItem";

type InboxListProps = {
  emails: Email[];
  selectedEmailId: string | null;
  onSelectEmail: (emailId: string) => void;
};

export default function InboxList({ emails, selectedEmailId, onSelectEmail }: InboxListProps) {
  const { t } = useTranslation();
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-fg">{t("inbox.heading")}</h2>
        <p className="text-xs text-fg-muted">{t("inbox.count", { count: emails.length })}</p>
        <p className="mt-0.5 text-[11px] text-fg-subtle">{t("inbox.keyboardHint")}</p>
      </div>
      <ul
        className="flex-1 divide-y divide-line-subtle overflow-y-auto"
        onKeyDown={inboxKeyHandler(
          emails.map((email) => email.id),
          selectedEmailId,
          onSelectEmail,
        )}
      >
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
