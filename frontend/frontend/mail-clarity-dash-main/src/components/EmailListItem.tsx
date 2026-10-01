import { useTranslation } from "react-i18next";

import type { Email } from "../types/email";
import { useFormat } from "../lib/useFormat";
import PriorityBadge from "./PriorityBadge";

type EmailListItemProps = {
  email: Email;
  selected: boolean;
  onSelect: (emailId: string) => void;
};

export default function EmailListItem({ email, selected, onSelect }: EmailListItemProps) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <li>
      <button
        type="button"
        aria-current={selected}
        data-email-id={email.id}
        onClick={() => onSelect(email.id)}
        className={`w-full border-l-2 px-4 py-3 text-left transition-colors ${
          selected ? "border-brand bg-brand-soft" : "border-transparent hover:bg-surface-muted"
        }`}
      >
        {/* First in the row, not after the sender: an sr-only label is absolutely positioned at
            where it would sit in flow, and after a truncated name that is past the list's right
            edge, which widened the list (and, with no positioned ancestor, the page: #96). */}
        {email.isRead ? null : <span className="sr-only">{t("inbox.unread")} </span>}
        <div className="flex items-baseline justify-between gap-2">
          <span
            aria-hidden="true"
            className={`mt-1.5 size-2 shrink-0 rounded-full ${
              email.isRead ? "bg-transparent" : "bg-brand"
            }`}
          />
          <span
            className={`flex-1 truncate text-sm text-fg ${
              email.isRead ? "font-normal" : "font-bold"
            }`}
          >
            {email.sender}
          </span>
          <span className="shrink-0 text-xs text-fg-subtle">
            {format.timestamp(email.timestamp)}
          </span>
        </div>
        <div
          className={`mt-0.5 truncate text-sm text-fg-body ${
            email.isRead ? "font-normal" : "font-semibold"
          }`}
        >
          {email.subject}
        </div>
        {email.masking === "pending" || email.masking === "abandoned" ? (
          <p className="mt-0.5 text-xs font-medium text-warning">
            {t(email.masking === "abandoned" ? "quarantine.abandonedBadge" : "quarantine.badge")}
          </p>
        ) : (
          <p className="mt-0.5 line-clamp-2 text-xs text-fg-muted">{email.preview}</p>
        )}
        <div className="mt-2">
          <PriorityBadge priority={email.priority} />
        </div>
      </button>
    </li>
  );
}
