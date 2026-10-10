import { Link } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { detailValues, restoreDetails } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { gmailThreadUrl } from "../lib/gmailLink";
import {
  useDismissEmail,
  useDraftFollowUp,
  useNotWaiting,
  useSaveWaitingDays,
  useSendFollowUp,
  useTodo,
} from "../lib/queries";
import { useFormat } from "../lib/useFormat";
import { cn } from "../lib/utils";
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
            title={t("todo.needsReview")}
            hint={t("todo.needsReviewHint")}
            section={todo.data.needsReview}
            detail={() => t("todo.flagged")}
          />
          <EmailSection
            title={t("todo.needsAction")}
            hint={t("todo.needsActionHint")}
            section={todo.data.needsAction}
            detail={(email) => email.actionItems.join(" · ")}
          />
          <WaitingSection waiting={todo.data.waiting} waitingDays={todo.data.waitingDays} />
          <EmailSection
            title={t("todo.unsentDrafts")}
            hint={t("todo.unsentDraftsHint")}
            section={todo.data.unsentDrafts}
            detail={(email) => email.draftReply}
            footer={
              <Link
                to="/drafts"
                className="inline-flex min-h-11 items-center text-sm font-medium text-brand hover:text-brand-strong md:min-h-0"
              >
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
                {/* min-w-48: on a phone the buttons wrap below the text instead of squeezing it. */}
                <Link to="/" search={{ email: email.id }} className="min-w-48 flex-1">
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
            <WaitingRow key={reply.id} reply={reply} />
          ))}
        </ul>
      )}
      {saveDays.isError ? (
        <p role="alert" className="text-xs text-danger">
          {errorMessage(saveDays.error, t, "todo.failed")}
        </p>
      ) : null}
    </section>
  );
}

/** One unanswered reply: open it, nudge in Gmail, or (sent through AIMail) draft and send a follow-up here. */
function WaitingRow({ reply }: { reply: WaitingReply }) {
  const { t } = useTranslation();
  const format = useFormat();
  const notWaiting = useNotWaiting();
  const draftFollowUp = useDraftFollowUp();
  const sendFollowUp = useSendFollowUp();
  // The follow-up being edited, with the real details in it as in the draft editor; null when closed.
  const [followUp, setFollowUp] = useState<string | null>(null);
  const values = detailValues(reply.email?.details);
  const failure = notWaiting.error ?? draftFollowUp.error ?? sendFollowUp.error;
  const startFollowUp = () =>
    draftFollowUp.mutate(reply.id, {
      onSuccess: ({ draft }) => setFollowUp(restoreDetails(draft, values)),
    });
  const send = (draft: string) =>
    sendFollowUp.mutate({ sentId: reply.id, draft }, { onSuccess: () => setFollowUp(null) });
  return (
    <li className="space-y-3 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-48 flex-1">
          <span className="block truncate text-sm text-fg-body">
            <DetailsContext.Provider value={values}>
              <WithDetails text={reply.email?.subject ?? reply.subject} />
            </DetailsContext.Provider>
          </span>
          <span className="block text-xs text-fg-muted">
            {t("todo.sentAgo", { when: format.timestamp(reply.sentAt), count: reply.workingDays })}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {reply.canFollowUp && followUp === null ? (
            <button
              type="button"
              disabled={draftFollowUp.isPending}
              onClick={startFollowUp}
              className={button({ intent: "primary", size: "xs" })}
            >
              {draftFollowUp.isPending ? t("todo.drafting") : t("todo.draftFollowUp")}
            </button>
          ) : null}
          {reply.email ? (
            <Link to="/" search={{ email: reply.email.id }} className={button({ size: "xs" })}>
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
      </div>
      {followUp === null ? null : (
        <div className="space-y-2">
          <label className="block text-xs font-medium text-fg-muted">
            {t("todo.followUpLabel")}
            <textarea
              value={followUp}
              onChange={(event) => setFollowUp(event.target.value)}
              disabled={sendFollowUp.isPending}
              rows={5}
              className={cn(field(), "mt-1 w-full resize-y text-sm")}
            />
          </label>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              disabled={sendFollowUp.isPending}
              onClick={() => setFollowUp(null)}
              className={button({ size: "sm" })}
            >
              {t("todo.cancelFollowUp")}
            </button>
            <button
              type="button"
              disabled={sendFollowUp.isPending || followUp.trim() === ""}
              onClick={() => send(followUp)}
              className={button({ intent: "primary", size: "sm" })}
            >
              {sendFollowUp.isPending ? t("todo.sendingFollowUp") : t("todo.sendFollowUp")}
            </button>
          </div>
        </div>
      )}
      {failure ? (
        <p role="alert" className="text-xs text-danger">
          {errorMessage(failure, t, "todo.followUpFailed")}
        </p>
      ) : null}
    </li>
  );
}
