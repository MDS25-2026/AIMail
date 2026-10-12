import { Link } from "@tanstack/react-router";
import { CircleCheck } from "lucide-react";
import { useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import { useTodo } from "../lib/queries";
import { chosenTab, TODO_TABS, tabCount, TodoTab } from "../lib/todoTabs";
import { useTodoActions, type TodoActions } from "../lib/useTodoActions";
import { cn } from "../lib/utils";
import type { Todo, TodoSection } from "../types/todo";
import { PageError, PageLoading } from "./PageState";
import TodoEmailRow, { type EmailTab } from "./TodoEmailRow";
import TodoWaiting from "./TodoWaiting";
import UndoNotice from "./UndoNotice";

// Enough to see what's most urgent without a scroll; the rest is one click away.
const SHOWN_AT_FIRST = 5;

const TAB_TITLE = {
  [TodoTab.Reply]: "todo.needsAction",
  [TodoTab.Review]: "todo.needsReview",
  [TodoTab.Drafts]: "todo.unsentDrafts",
  [TodoTab.Waiting]: "todo.waiting",
} as const;

const TAB_HINT = {
  [TodoTab.Reply]: "todo.needsActionHint",
  [TodoTab.Review]: "todo.needsReviewHint",
  [TodoTab.Drafts]: "todo.unsentDraftsHint",
  [TodoTab.Waiting]: "todo.waitingHint",
} as const;

type TodoPageProps = { tab?: TodoTab; onTab: (tab: TodoTab) => void };

/** What needs the reader, one list at a time (specs/features/todo-redesign-and-status.md). */
export default function TodoPage({ tab, onTab }: TodoPageProps) {
  const { t } = useTranslation();
  const todo = useTodo();
  const actions = useTodoActions();
  return (
    <section className="relative min-w-0 flex-1 space-y-5 overflow-y-auto bg-surface-muted p-4 md:p-6">
      <header>
        <h1 className="text-xl font-semibold text-fg">{t("todo.heading")}</h1>
        <p className="mt-1 text-sm text-fg-muted">
          {todo.data
            ? t("todo.progress", { done: todo.data.doneToday, left: todo.data.count })
            : t("todo.description")}
        </p>
      </header>
      {todo.isPending ? <PageLoading label={t("todo.heading")} /> : null}
      {todo.isError ? <PageError label={t("todo.heading")} error={todo.error} /> : null}
      {todo.data && todo.data.count === 0 ? <AllClear /> : null}
      {todo.data && todo.data.count > 0 ? (
        <TodoTabs
          todo={todo.data}
          tab={chosenTab(todo.data, tab)}
          onTab={onTab}
          actions={actions}
        />
      ) : null}
      <UndoNotice
        action={actions.notice}
        error={actions.error}
        onDone={actions.clear}
        onFailed={actions.failUndo}
      />
    </section>
  );
}

type TodoTabsProps = {
  todo: Todo;
  tab: TodoTab;
  onTab: (tab: TodoTab) => void;
  actions: TodoActions;
};

/** One tab per list; arrow keys move between them, as tabs do everywhere else. */
function TodoTabs({ todo, tab, onTab, actions }: TodoTabsProps) {
  const { t } = useTranslation();
  const tabRefs = useRef(new Map<TodoTab, HTMLButtonElement>());
  const panelId = `todo-panel-${tab}`;
  const move = (event: KeyboardEvent, current: TodoTab) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    const next =
      TODO_TABS[(TODO_TABS.indexOf(current) + step + TODO_TABS.length) % TODO_TABS.length];
    onTab(next);
    tabRefs.current.get(next)?.focus();
  };
  return (
    <div className="space-y-3">
      <div
        role="tablist"
        aria-label={t("todo.tabsLabel")}
        className="relative flex gap-1 overflow-x-auto border-b border-line"
      >
        {TODO_TABS.map((each) => (
          <button
            key={each}
            ref={(node) => {
              if (node) tabRefs.current.set(each, node);
            }}
            type="button"
            role="tab"
            id={`todo-tab-${each}`}
            aria-selected={each === tab}
            aria-controls={`todo-panel-${each}`}
            tabIndex={each === tab ? 0 : -1}
            onClick={() => onTab(each)}
            onKeyDown={(event) => move(event, each)}
            className={cn(
              "-mb-px flex min-h-11 shrink-0 items-center gap-2 border-b-2 px-3 text-sm whitespace-nowrap",
              each === tab
                ? "border-brand font-semibold text-fg"
                : "border-transparent text-fg-muted hover:text-fg",
            )}
          >
            {t(TAB_TITLE[each])}
            <span className="rounded-full bg-surface px-2 text-xs text-fg-muted">
              {tabCount(todo, each)}
            </span>
          </button>
        ))}
      </div>
      <div role="tabpanel" id={panelId} aria-labelledby={`todo-tab-${tab}`} className="space-y-2">
        <p className="text-xs text-fg-subtle">{t(TAB_HINT[tab])}</p>
        {tab === TodoTab.Waiting ? (
          <TodoWaiting waiting={todo.waiting} waitingDays={todo.waitingDays} actions={actions} />
        ) : (
          <EmailPanel key={tab} tab={tab} section={sectionFor(todo, tab)} actions={actions} />
        )}
      </div>
    </div>
  );
}

function sectionFor(todo: Todo, tab: EmailTab): TodoSection {
  switch (tab) {
    case TodoTab.Reply:
      return todo.needsAction;
    case TodoTab.Review:
      return todo.needsReview;
    case TodoTab.Drafts:
      return todo.unsentDrafts;
  }
}

function EmailPanel({
  tab,
  section,
  actions,
}: {
  tab: EmailTab;
  section: TodoSection;
  actions: TodoActions;
}) {
  const { t } = useTranslation();
  const [isShowingAll, setIsShowingAll] = useState(false);
  const shown = isShowingAll ? section.emails : section.emails.slice(0, SHOWN_AT_FIRST);
  const rest = section.emails.length - shown.length;
  if (section.emails.length === 0)
    return <p className="text-sm text-fg-muted">{t("todo.nothing")}</p>;
  return (
    <>
      <ul className="divide-y divide-line-subtle rounded-lg border border-line bg-surface">
        {shown.map((email) => (
          <TodoEmailRow key={email.id} email={email} tab={tab} actions={actions} />
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-4">
        {rest > 0 ? (
          <button
            type="button"
            onClick={() => setIsShowingAll(true)}
            className="min-h-11 text-sm font-medium text-brand hover:text-brand-strong md:min-h-0"
          >
            {t("todo.showRest", { count: rest })}
          </button>
        ) : null}
        {tab === TodoTab.Drafts ? (
          <Link
            to="/drafts"
            className="inline-flex min-h-11 items-center text-sm font-medium text-brand hover:text-brand-strong md:min-h-0"
          >
            {t("todo.allDrafts")}
          </Link>
        ) : null}
      </div>
    </>
  );
}

/** Nothing left: say so, and what will show up here, so a new reader knows what the page is for. */
function AllClear() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-line bg-surface px-6 py-10 text-center">
      <CircleCheck aria-hidden className="size-8 text-success" />
      <h2 className="text-lg font-semibold text-fg">{t("todo.allClearTitle")}</h2>
      <p className="max-w-md text-sm text-fg-muted">{t("todo.allClearBody")}</p>
      <Link to="/" className="text-sm font-medium text-brand hover:text-brand-strong">
        {t("todo.goToInbox")}
      </Link>
    </div>
  );
}
