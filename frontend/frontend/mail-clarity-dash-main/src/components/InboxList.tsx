import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { groupByThread } from "../lib/conversations";
import {
  CATEGORIES,
  filterByCategory,
  filterByPriority,
  PRIORITIES,
  type CategoryFilter,
  type PriorityFilter,
} from "../lib/inboxFilter";
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
  const listRef = useRef<HTMLUListElement>(null);
  // Filtering never touches the selection: an email the filter hides stays open in the detail panel.
  const [priority, setPriority] = useState<PriorityFilter>("all");
  const [category, setCategory] = useState<CategoryFilter>("all");
  const conversations = filterByCategory(
    filterByPriority(groupByThread(emails), priority),
    category,
  );
  const isFiltered = priority !== "all" || category !== "all";

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
        <div className="mt-2 flex gap-2">
          <label className="min-w-0 flex-1">
            <span className="sr-only">{t("inbox.filterLabel")}</span>
            <select
              value={priority}
              onChange={(event) => setPriority(event.target.value as PriorityFilter)}
              className={cn(field({ size: "sm" }), "w-full text-xs")}
            >
              <option value="all">{t("inbox.filterAll")}</option>
              {PRIORITIES.map((option) => (
                <option key={option} value={option}>
                  {t(`priority.${option}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-0 flex-1">
            <span className="sr-only">{t("inbox.categoryFilterLabel")}</span>
            <select
              value={category}
              onChange={(event) => setCategory(event.target.value as CategoryFilter)}
              className={cn(field({ size: "sm" }), "w-full text-xs")}
            >
              <option value="all">{t("inbox.categoryFilterAll")}</option>
              {CATEGORIES.map((option) => (
                <option key={option} value={option}>
                  {t(`category.${option}`)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="mt-2 text-[11px] text-fg-subtle">{t("inbox.keyboardHint")}</p>
      </div>
      {conversations.length === 0 && isFiltered ? (
        <p className="p-6 text-center text-sm text-fg-subtle">
          {category === "all" && priority !== "all"
            ? t("inbox.filterEmpty", { priority: t(`priority.${priority}`) })
            : t("inbox.filterEmptyAny")}
        </p>
      ) : null}
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
