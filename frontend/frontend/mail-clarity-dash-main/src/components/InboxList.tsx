import { useState } from "react";
import { useTranslation } from "react-i18next";

import { groupByThread } from "../lib/conversations";
import { filterByPriority, PRIORITIES, type PriorityFilter } from "../lib/inboxFilter";
import { inboxKeyHandler } from "../lib/inboxKeys";
import { cn } from "../lib/utils";
import type { Email } from "../types/email";
import EmailListItem from "./EmailListItem";
import { field } from "./variants";

type InboxListProps = {
  emails: Email[];
  selectedEmailId: string | null;
  onSelectEmail: (emailId: string) => void;
};

export default function InboxList({ emails, selectedEmailId, onSelectEmail }: InboxListProps) {
  const { t } = useTranslation();
  // Filtering never touches the selection: an email the filter hides stays open in the detail panel.
  const [priority, setPriority] = useState<PriorityFilter>("all");
  const conversations = filterByPriority(groupByThread(emails), priority);
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-fg">{t("inbox.heading")}</h2>
            <p className="text-xs text-fg-muted">
              {t("inbox.conversations", { count: conversations.length })}
            </p>
          </div>
          <label>
            <span className="sr-only">{t("inbox.filterLabel")}</span>
            <select
              value={priority}
              onChange={(event) => setPriority(event.target.value as PriorityFilter)}
              className={cn(field({ size: "sm" }), "text-xs")}
            >
              <option value="all">{t("inbox.filterAll")}</option>
              {PRIORITIES.map((option) => (
                <option key={option} value={option}>
                  {t(`priority.${option}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="mt-0.5 text-[11px] text-fg-subtle">{t("inbox.keyboardHint")}</p>
      </div>
      {conversations.length === 0 && priority !== "all" ? (
        <p className="p-6 text-center text-sm text-fg-subtle">
          {t("inbox.filterEmpty", { priority: t(`priority.${priority}`) })}
        </p>
      ) : null}
      <ul
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
        {conversations.map(({ email, count, isRead }) => (
          <EmailListItem
            key={email.id}
            email={{ ...email, isRead }}
            messageCount={count}
            selected={email.id === selectedEmailId}
            onSelect={onSelectEmail}
          />
        ))}
      </ul>
    </div>
  );
}
