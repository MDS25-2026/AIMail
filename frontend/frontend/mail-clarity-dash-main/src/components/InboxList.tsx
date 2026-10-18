import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import { groupByThread } from "../lib/conversations";
import {
  CATEGORIES,
  filterByCategory,
  filterByPriority,
  filterByView,
  INBOX_VIEWS,
  PRIORITIES,
  sortConversations,
  unreadCount,
  type CategoryFilter,
  type InboxSort,
  type InboxView,
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
  /** Primary or Updates (#238); the page keeps it in the URL. */
  view: InboxView;
  onViewChange: (view: InboxView) => void;
  /** Older pages not loaded yet: an empty tab may only look empty. */
  hasOlder?: boolean;
};

export default function InboxList({
  emails,
  selectedEmailId,
  onSelectEmail,
  view,
  onViewChange,
  hasOlder = false,
}: InboxListProps) {
  const { t } = useTranslation();
  const listRef = useRef<HTMLUListElement>(null);
  // Filtering never touches the selection: an email the filter hides stays open in the detail panel.
  const [priority, setPriority] = useState<PriorityFilter>("all");
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [sort, setSort] = useState<InboxSort>("urgent");
  const all = groupByThread(emails);
  const conversations = sortConversations(
    filterByCategory(filterByPriority(filterByView(all, view), priority), category),
    sort,
  );
  const unreadUpdates = unreadCount(filterByView(all, "updates"));
  const isFiltered = priority !== "all" || category !== "all";

  useEffect(() => {
    if (selectedEmailId && listRef.current) {
      const selectedEl = listRef.current.querySelector<HTMLElement>('[aria-current="true"]');
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  }, [selectedEmailId]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h1 className="text-sm font-semibold text-fg">{t("inbox.heading")}</h1>
            <p className="text-xs text-fg-muted">
              {t("inbox.conversations", { count: conversations.length })}
            </p>
          </div>
          <label className="shrink-0">
            <span className="sr-only">{t("inbox.sortLabel")}</span>
            <select
              value={sort}
              onChange={(event) => setSort(event.target.value as InboxSort)}
              className={cn(field({ size: "sm" }), "text-xs")}
            >
              <option value="urgent">{t("inbox.sortUrgent")}</option>
              <option value="newest">{t("inbox.sortNewest")}</option>
            </select>
          </label>
        </div>
        <ViewTabs view={view} onViewChange={onViewChange} unreadUpdates={unreadUpdates} />
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
        <p className="mt-2 hidden text-[11px] text-fg-subtle md:block">{t("inbox.keyboardHint")}</p>
      </div>
      <div
        role="tabpanel"
        id={`inbox-panel-${view}`}
        aria-labelledby={`inbox-tab-${view}`}
        className="flex min-h-0 flex-1 flex-col"
      >
        {view === "updates" ? (
          <p className="border-b border-line-subtle px-4 py-2 text-xs text-fg-muted">
            {t("inbox.updatesHint")}
          </p>
        ) : null}
        {conversations.length === 0 && isFiltered ? (
          <p className="p-6 text-center text-sm text-fg-subtle">
            {category === "all" && priority !== "all"
              ? t("inbox.filterEmpty", { priority: t(`priority.${priority}`) })
              : t("inbox.filterEmptyAny")}
          </p>
        ) : null}
        {/* Not while Load older may still bring some: page 1 can be all newsletters. */}
        {conversations.length === 0 && !isFiltered && !hasOlder ? (
          <p className="p-6 text-center text-sm text-fg-subtle">
            {t(view === "updates" ? "inbox.updatesEmpty" : "inbox.primaryEmpty")}
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
    </div>
  );
}

/** Primary and Updates as tabs; arrow keys move between them, as on the To-do page. */
function ViewTabs({
  view,
  onViewChange,
  unreadUpdates,
}: {
  view: InboxView;
  onViewChange: (view: InboxView) => void;
  unreadUpdates: number;
}) {
  const { t } = useTranslation();
  const tabRefs = useRef(new Map<InboxView, HTMLButtonElement>());
  const move = (event: KeyboardEvent, current: InboxView) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    const at = INBOX_VIEWS.indexOf(current);
    const next = INBOX_VIEWS[(at + step + INBOX_VIEWS.length) % INBOX_VIEWS.length];
    onViewChange(next);
    tabRefs.current.get(next)?.focus();
  };
  return (
    <div
      role="tablist"
      aria-label={t("inbox.viewsLabel")}
      className="mt-2 flex gap-1 border-b border-line"
    >
      {INBOX_VIEWS.map((each) => (
        <button
          key={each}
          ref={(node) => {
            if (node) tabRefs.current.set(each, node);
          }}
          type="button"
          role="tab"
          id={`inbox-tab-${each}`}
          aria-selected={each === view}
          // Only the selected tab's panel is rendered.
          aria-controls={each === view ? `inbox-panel-${each}` : undefined}
          tabIndex={each === view ? 0 : -1}
          onClick={() => onViewChange(each)}
          onKeyDown={(event) => move(event, each)}
          className={cn(
            "-mb-px flex min-h-11 items-center gap-1.5 border-b-2 px-3 text-xs md:min-h-9",
            each === view
              ? "border-brand font-semibold text-fg"
              : "border-transparent text-fg-muted hover:text-fg",
          )}
        >
          {t(each === "updates" ? "inbox.viewUpdates" : "inbox.viewPrimary")}
          {each === "updates" && unreadUpdates > 0 ? (
            <span className="rounded-full bg-brand-soft px-1.5 text-[11px] font-semibold text-brand">
              <span aria-hidden>{unreadUpdates}</span>
              <span className="sr-only">{t("inbox.unread", { count: unreadUpdates })}</span>
            </span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
