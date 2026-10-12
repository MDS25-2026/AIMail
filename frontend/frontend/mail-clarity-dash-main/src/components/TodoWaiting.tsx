import { useNavigate } from "@tanstack/react-router";
import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { detailValues, restoreDetails } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { useDetailsHidden } from "../lib/detailsVisibility";
import { findTemplatePlaceholders } from "../lib/draftGuards";
import { gmailThreadUrl } from "../lib/gmailLink";
import { useDraftFollowUp, useSaveWaitingDays, useSendFollowUp } from "../lib/queries";
import { checkTone } from "../lib/toneCheck";
import type { TodoActions } from "../lib/useTodoActions";
import { useFormat } from "../lib/useFormat";
import { cn } from "../lib/utils";
import type { WaitingReply } from "../types/todo";
import RowMenu, { type MenuItem } from "./RowMenu";
import { button, field } from "./variants";
import WithDetails from "./WithDetails";

const WAITING_DAY_CHOICES = [1, 2, 3, 4, 5, 7, 10, 14] as const;

type WaitingPanelProps = { waiting: WaitingReply[]; waitingDays: number; actions: TodoActions };

/** The Waiting on others tab: replies of the reader's still without an answer. */
export default function WaitingPanel({ waiting, waitingDays, actions }: WaitingPanelProps) {
  const { t } = useTranslation();
  const saveDays = useSaveWaitingDays();
  return (
    <div className="space-y-2">
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
            <WaitingRow key={reply.id} reply={reply} actions={actions} />
          ))}
        </ul>
      )}
      {saveDays.isError ? (
        <p role="alert" className="text-xs text-danger">
          {errorMessage(saveDays.error, t, "todo.failed")}
        </p>
      ) : null}
    </div>
  );
}

/** One unanswered reply: open it, nudge in Gmail, or (sent through AIMail) draft and send a follow-up here. */
function WaitingRow({ reply, actions }: { reply: WaitingReply; actions: TodoActions }) {
  const { t } = useTranslation();
  const format = useFormat();
  const navigate = useNavigate();
  const draftFollowUp = useDraftFollowUp();
  const sendFollowUp = useSendFollowUp();
  const [isHidingDetails] = useDetailsHidden();
  // The follow-up being edited, shown like the draft editor (real details unless hidden); null when closed.
  const [followUp, setFollowUp] = useState<string | null>(null);
  // Set by the first Send when the text needs a second look; the next press sends anyway.
  const [warning, setWarning] = useState<string | null>(null);
  const values = detailValues(reply.email?.details);
  const failure = draftFollowUp.error ?? sendFollowUp.error;
  const gmail = gmailThreadUrl(reply.threadId);
  const openHere = reply.email;
  const items: MenuItem[] = [
    { label: t("todo.notWaiting"), onSelect: () => actions.notWaiting(reply.id) },
    ...(openHere
      ? [
          {
            label: t("todo.openHere"),
            onSelect: () => void navigate({ to: "/", search: { email: openHere.id } }),
          },
        ]
      : []),
    ...(reply.canFollowUp ? [{ label: t("todo.openInGmail"), href: gmail }] : []),
  ];
  const open = (text: string | null) => {
    setFollowUp(text);
    setWarning(null);
  };
  const startFollowUp = () =>
    draftFollowUp.mutate(reply.id, {
      // Filled from the thread the draft is numbered in: the same names the send will use.
      onSuccess: ({ draft, details }) =>
        open(isHidingDetails ? draft : restoreDetails(draft, detailValues(details))),
    });
  const send = (draft: string) => {
    const needsLook = warning === null ? followUpWarning(draft, t) : null;
    if (needsLook) {
      setWarning(needsLook);
      return;
    }
    sendFollowUp.mutate({ sentId: reply.id, draft }, { onSuccess: () => open(null) });
  };
  return (
    <li className="space-y-3 px-4 py-3">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-48 flex-1 space-y-0.5">
          <p className="text-sm font-medium text-fg">
            {t("todo.next.waiting", { count: reply.workingDays })}
          </p>
          <p className="truncate text-xs text-fg-muted">
            <DetailsContext.Provider value={values}>
              <WithDetails text={reply.email?.subject ?? reply.subject} />
            </DetailsContext.Provider>
            {" · "}
            {t("todo.sentOn", { when: format.timestamp(reply.sentAt) })}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {/* Sent from Gmail, the follow-up is written there; through AIMail, it's drafted here. */}
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
          {reply.canFollowUp ? null : (
            <a
              href={gmail}
              target="_blank"
              rel="noopener noreferrer"
              className={button({ intent: "primary", size: "xs" })}
            >
              {t("todo.openInGmail")}
            </a>
          )}
          <RowMenu items={items} />
        </div>
      </div>
      {followUp === null ? null : (
        <div className="space-y-2">
          <label className="block text-xs font-medium text-fg-muted">
            {t("todo.followUpLabel")}
            <textarea
              value={followUp}
              onChange={(event) => open(event.target.value)}
              disabled={sendFollowUp.isPending}
              rows={5}
              className={cn(field(), "mt-1 w-full resize-y text-sm")}
            />
          </label>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              disabled={sendFollowUp.isPending}
              onClick={() => open(null)}
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
              {sendFollowUp.isPending
                ? t("todo.sendingFollowUp")
                : warning
                  ? t("draftStatus.sendAnyway")
                  : t("todo.sendFollowUp")}
            </button>
          </div>
          {warning ? (
            <p role="alert" className="text-xs text-warning">
              {warning}
            </p>
          ) : null}
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

/** What the draft editor would ask about before sending: text left for the reader, or the tone. */
function followUpWarning(draft: string, t: TFunction): string | null {
  const placeholders = findTemplatePlaceholders(draft).length;
  if (placeholders > 0) return t("draftStatus.sendTemplates", { count: placeholders });
  return checkTone(draft).hasIssues ? t("draftStatus.toneWarning") : null;
}
