import { Link } from "@tanstack/react-router";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { detailValues } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { gmailThreadUrl } from "../lib/gmailLink";
import { nextStep, TodoTab } from "../lib/todoTabs";
import type { TodoActions } from "../lib/useTodoActions";
import type { Email, Priority } from "../types/email";
import PriorityBadge from "./PriorityBadge";
import RowMenu, { type MenuItem } from "./RowMenu";
import { button } from "./variants";
import WithDetails, { SenderText } from "./WithDetails";

export type EmailTab = TodoTab.Reply | TodoTab.Review | TodoTab.Drafts;

const PRIMARY_LABEL = {
  [TodoTab.Reply]: "todo.reply",
  [TodoTab.Review]: "todo.reviewDraft",
  [TodoTab.Drafts]: "todo.openDraft",
} as const;

// Only these earn a badge on the row; the rest would be noise on every line.
const BADGED: ReadonlySet<Priority> = new Set(["critical", "high"]);

type TodoEmailRowProps = { email: Email; tab: EmailTab; actions: TodoActions };

/** One to-do: the next step first, one main button, the rest in a menu, more on request. */
export default function TodoEmailRow({ email, tab, actions }: TodoEmailRowProps) {
  const { t } = useTranslation();
  const moreId = useId();
  const [isExpanded, setIsExpanded] = useState(false);
  const items: MenuItem[] = [
    { label: t("todo.dismissShort"), onSelect: () => actions.dismiss(email.id) },
    ...(email.threadId
      ? [{ label: t("todo.openInGmail"), href: gmailThreadUrl(email.threadId) }]
      : []),
  ];
  return (
    <li className="px-4 py-3">
      {/* The row's own details, so it reads "Aisyah" where the inbox does, not [PERSON_1]. */}
      <DetailsContext.Provider value={detailValues(email.details)}>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-48 flex-1 space-y-0.5">
            <p className="flex items-start gap-2 text-sm font-medium text-fg">
              {BADGED.has(email.priority) ? <PriorityBadge priority={email.priority} /> : null}
              <span className="line-clamp-2">
                <WithDetails text={nextStep(tab, email, t)} />
              </span>
            </p>
            <p className="truncate text-xs text-fg-muted">
              <SenderText sender={email.sender} /> · <WithDetails text={email.subject} />
            </p>
            <button
              type="button"
              aria-expanded={isExpanded}
              aria-controls={moreId}
              onClick={() => setIsExpanded((open) => !open)}
              className="min-h-11 text-xs font-medium text-brand hover:text-brand-strong md:min-h-0"
            >
              {isExpanded ? t("todo.hideDetails") : t("todo.showDetails")}
            </button>
            {isExpanded ? <RowDetails id={moreId} email={email} /> : null}
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Link
              to="/"
              search={{ email: email.id }}
              className={button({ intent: "primary", size: "xs" })}
            >
              {t(PRIMARY_LABEL[tab])}
            </Link>
            <RowMenu items={items} onRemind={(choice) => actions.remind(email.id, choice)} />
          </div>
        </div>
      </DetailsContext.Provider>
    </li>
  );
}

/** The first level of detail: what it's about, what's asked, how the draft starts. */
function RowDetails({ id, email }: { id: string; email: Email }) {
  const { t } = useTranslation();
  return (
    <dl id={id} className="mt-2 space-y-2 rounded-md bg-surface-muted p-3 text-xs">
      {email.aiSummary ? (
        <div>
          <dt className="font-semibold text-fg-muted">{t("todo.summaryLabel")}</dt>
          <dd className="text-fg-body">
            <WithDetails text={email.aiSummary} />
          </dd>
        </div>
      ) : null}
      {email.actionItems.length > 0 ? (
        <div>
          <dt className="font-semibold text-fg-muted">{t("todo.actionItemsLabel")}</dt>
          <dd>
            <ul className="list-disc pl-4 text-fg-body">
              {email.actionItems.map((item) => (
                <li key={item}>
                  <WithDetails text={item} />
                </li>
              ))}
            </ul>
          </dd>
        </div>
      ) : null}
      {email.draftReply ? (
        <div>
          <dt className="font-semibold text-fg-muted">{t("todo.draftStarts")}</dt>
          <dd className="line-clamp-3 whitespace-pre-line text-fg-body">
            <WithDetails text={email.draftReply} />
          </dd>
        </div>
      ) : null}
    </dl>
  );
}
