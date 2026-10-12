import type { TFunction } from "i18next";

import type { Email } from "../types/email";
import type { Todo } from "../types/todo";
import { reviewReasonText } from "./reviewReasons";

/** The four lists, in the order the page shows them (specs/features/todo-redesign-and-status.md). */
export enum TodoTab {
  Reply = "reply",
  Review = "review",
  Drafts = "drafts",
  Waiting = "waiting",
}

export const TODO_TABS = [TodoTab.Reply, TodoTab.Review, TodoTab.Drafts, TodoTab.Waiting] as const;

const TAB_VALUES = new Set<string>(TODO_TABS);

export function parseTab(value: unknown): TodoTab | undefined {
  return typeof value === "string" && TAB_VALUES.has(value) ? (value as TodoTab) : undefined;
}

export function tabCount(todo: Todo, tab: TodoTab): number {
  switch (tab) {
    case TodoTab.Reply:
      return todo.needsAction.total;
    case TodoTab.Review:
      return todo.needsReview.total;
    case TodoTab.Drafts:
      return todo.unsentDrafts.total;
    case TodoTab.Waiting:
      return todo.waiting.length;
  }
}

/** The tab asked for in the address, else the first with anything in it. */
export function chosenTab(todo: Todo, requested: TodoTab | undefined): TodoTab {
  if (requested) return requested;
  return TODO_TABS.find((tab) => tabCount(todo, tab) > 0) ?? TodoTab.Reply;
}

/** The row's first line: a verb and the concrete step, never an empty verb. */
export function nextStep(
  tab: TodoTab.Reply | TodoTab.Review | TodoTab.Drafts,
  email: Email,
  t: TFunction,
): string {
  if (tab === TodoTab.Drafts) return t("todo.next.drafts");
  if (tab === TodoTab.Review) {
    const [reason] = email.reviewReasons ?? [];
    return t("todo.next.review", {
      reason: reason ? reviewReasonText(reason, t) : t("todo.flagged"),
    });
  }
  // Action items already start with a verb ("Confirm the date"); a "Reply:" before them read twice.
  const [first, ...rest] = email.actionItems;
  if (first === undefined) return t("todo.next.reply", { item: email.aiSummary || email.subject });
  return rest.length > 0 ? `${first} ${t("todo.next.more", { count: rest.length })}` : first;
}
