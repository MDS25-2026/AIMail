import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { detailValues } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { gmailThreadUrl } from "../lib/gmailLink";
import { useDismissEmail, useNotWaiting, useSaveWaitingDays, useTodo } from "../lib/queries";
import { useFormat } from "../lib/useFormat";
import type { Email } from "../types/email";
import type { TodoSection, WaitingReply } from "../types/todo";
import { PageError, PageLoading } from "./PageState";
import { button, field } from "./variants";
import WithDetails from "./WithDetails";

const WAITING_DAY_CHOICES = [1, 2, 3, 4, 5, 7, 10, 14] as const;

/** What needs the reader (specs/features/todo-page.md). */
export default function TodoPage() {
  const { t } = useTranslation();
  const todo = useTodo();
  return (
    <section className="relative min-w-0 flex-1 space-y-6 overflow-y-auto bg-surface-muted p-6">
      <header>
        <h1 className="text-xl font-semibold text-fg">{t("todo.heading")}</h1>
        <p className="mt-1 text-sm text-fg-muted">{t("todo.description")}</p>
      </header>
      {todo.isPending ? <PageLoading label={t("todo.heading")} /> : null}
      {todo.isError ? <PageError label={t("todo.heading")} error={todo.error} /> : null}
      {todo.data ? (
        <>
          <EmailSection
            title={t("todo.needsAction")}
            hint={t("todo.needsActionHint")}
            section={todo.data.needsAction}
            detail={(email) => email.actionItems.join(" · ")}
          />
          <EmailSection
            title={t("todo.needsReview")}
            hint={t("todo.needsReviewHint")}
            section={todo.data.needsReview}
            detail={() => t("todo.flagged")}
          />
          <WaitingSection waiting={todo.data.waiting} waitingDays={todo.data.waitingDays} />
          <EmailSection
            title={t("todo.unsentDrafts")}
            hint={t("todo.unsentDraftsHint")}
            section={todo.data.unsentDrafts}
            detail={(email) => email.draftReply}
            footer={
              <Link to="/drafts" className="text-sm font-medium text-brand hover:text-brand-strong">
                {t("todo.allDrafts")}
              </Link>
            }
          />
        </>
      ) : null}
    </section>
  );
}

type EmailSectionProps = {
  title: string;
  hint: string;
  section: TodoSection;
  detail: (email: Email) => string;
  footer?: ReactNode;
};

function EmailSection({ title, hint, section, detail, footer }: EmailSectionProps) {
  const { t } = useTranslation();
  const dismiss = useDismissEmail();
  return (
    <section aria-label={title} className="space-y-2">
      <h2 className="text-sm font-semibold text-fg">
        {title} <span className="font-normal text-fg-muted">({section.total})</span>
      </h2>
      <p className="text-xs text-fg-subtle">{hint}</p>
      {section.emails.length === 0 ? (
        <p className="text-sm text-fg-muted">{t("todo.nothing")}</p>
      ) : (
        <ul className="relative divide-y divide-line-subtle overflow-hidden rounded-lg border border-line bg-surface">
          {section.emails.map((email) => (
            <li key={email.id} className="flex items-start justify-between gap-3 px-4 py-3">
              {/* The row's own details, so it reads "Aisyah" where the inbox does, not [PERSON_1]. */}
              <DetailsContext.Provider value={detailValues(email.details)}>
                <Link to="/" search={{ email: email.id }} className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-fg">
                    {email.sender}
                  </span>
                  <span className="block truncate text-sm text-fg-body">
                    <WithDetails text={email.subject} />
                  </span>
                  <span className="mt-0.5 line-clamp-1 block text-xs text-fg-muted">
                    <WithDetails text={detail(email)} />
                  </span>
                </Link>
              </DetailsContext.Provider>
              <button
                type="button"
                disabled={dismiss.isPending}
                onClick={() => dismiss.mutate(email.id)}
                className={button({ size: "xs" })}
              >
                {t("todo.noReplyNeeded")}
              </button>
            </li>
          ))}
        </ul>
      )}
      {dismiss.isError ? (
        <p role="alert" className="text-xs text-danger">
          {errorMessage(dismiss.error, t, "todo.failed")}
        </p>
      ) : null}
      {footer}
    </section>
  );
}

function WaitingSection({
  waiting,
  waitingDays,
}: {
  waiting: WaitingReply[];
  waitingDays: number;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const notWaiting = useNotWaiting();
  const saveDays = useSaveWaitingDays();
  const title = t("todo.waiting");
  return (
    <section aria-label={title} className="space-y-2">
      <h2 className="text-sm font-semibold text-fg">
        {title} <span className="font-normal text-fg-muted">({waiting.length})</span>
      </h2>
      <label className="flex items-center gap-2 text-xs text-fg-subtle">
        {t("todo.waitingAfter")}
        <select
          value={waitingDays}
          disabled={saveDays.isPending}
          onChange={(event) => saveDays.mutate(Number(event.target.value))}
          className={field({ size: "sm" })}
        >
          {WAITING_DAY_CHOICES.map((days) => (
            <option key={days} value={days}>
              {t("todo.workingDays", { count: days })}
            </option>
          ))}
        </select>
      </label>
      {waiting.length === 0 ? (
        <p className="text-sm text-fg-muted">{t("todo.nothingWaiting")}</p>
      ) : (
        <ul className="relative divide-y divide-line-subtle overflow-hidden rounded-lg border border-line bg-surface">
          {waiting.map((reply) => (
            <li
              key={reply.id}
              className="flex flex-wrap items-start justify-between gap-3 px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <span className="block truncate text-sm text-fg-body">
                  <DetailsContext.Provider value={detailValues(reply.email?.details)}>
                    <WithDetails text={reply.email?.subject ?? reply.subject} />
                  </DetailsContext.Provider>
                </span>
                <span className="block text-xs text-fg-muted">
                  {t("todo.sentAgo", {
                    when: format.timestamp(reply.sentAt),
                    count: reply.workingDays,
                  })}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {reply.email ? (
                  <Link
                    to="/"
                    search={{ email: reply.email.id }}
                    className={button({ size: "xs" })}
                  >
                    {t("todo.openHere")}
                  </Link>
                ) : null}
                <a
                  href={gmailThreadUrl(reply.threadId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={button({ size: "xs" })}
                >
                  {t("todo.openInGmail")}
                </a>
                <button
                  type="button"
                  disabled={notWaiting.isPending}
                  onClick={() => notWaiting.mutate(reply.id)}
                  className={button({ size: "xs" })}
                >
                  {t("todo.notWaiting")}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      {notWaiting.isError || saveDays.isError ? (
        <p role="alert" className="text-xs text-danger">
          {errorMessage(notWaiting.error ?? saveDays.error, t, "todo.failed")}
        </p>
      ) : null}
    </section>
  );
}
