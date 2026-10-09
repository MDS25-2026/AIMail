import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { groupByThread } from "../lib/conversations";
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
  const listRef = useRef<HTMLUListElement>(null);
  const conversations = groupByThread(emails);

  useEffect(() => {
    if (selectedEmailId && listRef.current) {
      const selectedEl = listRef.current.querySelector<HTMLElement>('[aria-current="true"]');
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  }, [selectedEmailId, conversations]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-fg">{t("inbox.heading")}</h2>
        <p className="text-xs text-fg-muted">
          {t("inbox.conversations", { count: conversations.length })}
        </p>
        <p className="mt-0.5 text-[11px] text-fg-subtle">{t("inbox.keyboardHint")}</p>
      </div>
      <ul
        ref={listRef}
        // relative: each unread row carries an absolutely positioned sr-only label; without a
        // positioned ancestor inside this scroller it positioned against the page, and 21 of them
        // stretched the document to 4211px on a 900px viewport (#96, measured).
        className="relative min-h-0 flex-1 divide-y divide-line-subtle overflow-y-auto"
        onKeyDown={inboxKeyHandler(
          conversations.map(({ email }) => email.id),
          selectedEmailId,
          onSelectEmail,
        )}
      >
        {conversations.map(({ email, count, isRead, messageIds }) => {
          const isSelected =
            email.id === selectedEmailId || messageIds.includes(selectedEmailId ?? "");
          return (
            <EmailListItem
              key={email.id}
              email={{ ...email, isRead }}
              messageCount={count}
              selected={isSelected}
              onSelect={onSelectEmail}
            />
          );
        })}
      </ul>
    </div>
  );
}
