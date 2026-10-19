import { useMemo } from "react";
import { ArrowLeft, Bot, Paperclip, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { splitAround } from "../lib/conversations";
import { detailValues, maskSender } from "../lib/details";
import { DetailsContext, useDetailValues } from "../lib/detailsContext";
import { useDetailsHidden } from "../lib/detailsVisibility";
import { DraftAvailability, draftAvailability } from "../lib/draftAvailability";
import { gmailThreadUrl } from "../lib/gmailLink";
import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import { useFormat } from "../lib/useFormat";
import { AuthStatus, type Email } from "../types/email";
import ActionItemsList from "./ActionItemsList";
import AISummaryCard from "./AISummaryCard";
import ConversationMessages from "./ConversationMessages";
import DetailsToggle from "./DetailsToggle";
import DraftActionsBar from "./DraftActionsBar";
import DraftGate from "./DraftGate";
import DraftReplyEditor from "./DraftReplyEditor";
import DraftStatus from "./DraftStatus";
import EmailBody from "./EmailBody";
import HiddenDetailChips from "./HiddenDetailChips";
import MissingDetailsNotice from "./MissingDetailsNotice";
import PriorityBadge from "./PriorityBadge";
import PrivacyReceipt from "./PrivacyReceipt";
import RefineInput from "./RefineInput";
import TranslateDraft from "./TranslateDraft";
import ScheduleBanner from "./ScheduleBanner";
import SnoozeMenu from "./SnoozeMenu";
import SourcesChips from "./SourcesChips";
import TemplatePicker from "./TemplatePicker";
import UseAsExampleButton from "./UseAsExampleButton";
import WithDetails from "./WithDetails";
import { button } from "./variants";

/** onBack and the read toggles come from the inbox page; the extension panel has none. */
type EmailDetailPanelProps = {
  email: Email | null;
  workflow: DraftWorkflow;
  onBack?: () => void;
  onMarkUnread?: (emailId: string) => void;
  onMarkRead?: (emailId: string) => void;
};

export default function EmailDetailPanel({
  email,
  workflow,
  onBack,
  onMarkUnread,
  onMarkRead,
}: EmailDetailPanelProps) {
  const { t } = useTranslation();
  if (!email) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-sm text-fg-subtle">
        {t("detail.empty")}
      </div>
    );
  }

  const availability = draftAvailability(email);
  // Quarantined (#109): nothing to read or draft from until the listener can mask the content.
  if (availability === DraftAvailability.Quarantined) {
    return (
      <div className="relative h-full overflow-y-auto">
        <DetailHeader
          email={email}
          onBack={onBack}
          onMarkUnread={onMarkUnread}
          onMarkRead={onMarkRead}
        />
        <div className="space-y-4 p-6">
          <SenderLine email={email} />
          <DraftGate email={email} availability={availability}>
            {null}
          </DraftGate>
        </div>
      </div>
    );
  }

  const conversation = splitAround(email.threadContext, email.timestamp);
  const values = useMemo(() => detailValues(email.details), [email.details]);
  return (
    <DetailsContext.Provider value={values}>
      <div className="relative h-full overflow-y-auto">
        <DetailHeader
          email={email}
          onBack={onBack}
          onMarkUnread={onMarkUnread}
          onMarkRead={onMarkRead}
        />
        {/* The end of the draft clears the phone's fixed send bar and the home indicator. */}
        <div className="space-y-4 p-4 pb-[calc(10rem+env(safe-area-inset-bottom))] md:p-6">
          <SenderLine email={email} />
          <MissingDetailsNotice email={email} draft={workflow.draft} />
          <ConversationMessages messages={conversation.earlier} />
          <EmailBody key={email.id} email={email} />
          {email.hasUnreadAttachment ? <UnreadAttachmentNotice email={email} /> : null}
          <ConversationMessages messages={conversation.later} />
          <AISummaryCard summary={email.aiSummary} />
          <ActionItemsList items={email.actionItems} />
          <DraftGate email={email} availability={availability}>
            <DraftSection email={email} workflow={workflow} />
          </DraftGate>
        </div>
      </div>
    </DetailsContext.Provider>
  );
}

function SenderLine({ email }: { email: Email }) {
  const { t } = useTranslation();
  const format = useFormat();
  const [isHidden] = useDetailsHidden();
  const contextValues = useDetailValues();
  const values = contextValues.size > 0 ? contextValues : detailValues(email.details);
  const sender = maskSender(email.sender, isHidden, values);
  return (
    <p className="text-sm text-fg-muted">
      {t("detail.fromAt", { sender, when: format.timestamp(email.timestamp) })}
    </p>
  );
}

/** Said, not silent: the listener couldn't read an attachment, so the reader opens it in Gmail. */
function UnreadAttachmentNotice({ email }: { email: Email }) {
  const { t } = useTranslation();
  return (
    <p className="flex flex-wrap items-center gap-2 rounded-md bg-surface-muted px-3 py-2 text-xs text-fg-muted">
      <Paperclip aria-hidden className="size-3.5 shrink-0" />
      <span className="min-w-0 flex-1">{t("detail.unreadAttachment")}</span>
      {email.threadId ? (
        <a
          href={gmailThreadUrl(email.threadId)}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-brand hover:text-brand-strong"
        >
          {t("detail.openInGmail")}
        </a>
      ) : null}
    </p>
  );
}

type DetailHeaderProps = {
  email: Email;
  onBack?: () => void;
  onMarkUnread?: (emailId: string) => void;
  onMarkRead?: (emailId: string) => void;
};

function DetailHeader({ email, onBack, onMarkUnread, onMarkRead }: DetailHeaderProps) {
  const { t } = useTranslation();
  return (
    // Stays at the top while the email scrolls, so its actions are always in reach; one row, so a
    // phone keeps room to read between it and the fixed send bar.
    <header className="sticky top-0 z-20 border-b border-line bg-surface px-4 py-3 md:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {onBack ? <BackToInbox onBack={onBack} /> : null}
          <h2 className="min-w-0 truncate text-base font-semibold text-fg" title={email.subject}>
            <WithDetails text={email.subject} />
          </h2>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          {email.authStatus === AuthStatus.SpoofDetected ? (
            <span className="flex items-center gap-1 rounded bg-danger-soft px-2 py-0.5 text-xs font-semibold text-danger">
              <ShieldAlert aria-hidden className="size-3.5" />
              {t("security.spoofBadge")}
            </span>
          ) : null}
          {/* A toggle, so it stays: one use used to remove it (test run T10). */}
          {onMarkUnread && email.isRead ? (
            <button
              type="button"
              onClick={() => onMarkUnread(email.id)}
              className={button({ size: "xs" })}
            >
              {t("detail.markUnread")}
            </button>
          ) : null}
          {onMarkRead && !email.isRead ? (
            <button
              type="button"
              onClick={() => onMarkRead(email.id)}
              className={button({ size: "xs" })}
            >
              {t("detail.markRead")}
            </button>
          ) : null}
          <SnoozeMenu key={`snooze-${email.id}`} email={email} />
          <PrivacyReceipt email={email} />
          {email.details?.length ? <DetailsToggle /> : null}
          <PriorityBadge priority={email.priority} />
        </div>
      </div>
    </header>
  );
}

function DraftSection({ email, workflow }: { email: Email; workflow: DraftWorkflow }) {
  const { t } = useTranslation();
  const format = useFormat();
  const values = useMemo(() => detailValues(email.details), [email.details]);
  return (
    <section className="space-y-4 rounded-lg border border-line bg-surface p-4">
      {email.isAutomated && !email.draftReply ? (
        <p
          role="status"
          className="flex gap-2 rounded-md border border-line bg-surface-muted px-3 py-2 text-xs text-fg-body"
        >
          <Bot aria-hidden className="mt-0.5 size-4 shrink-0 text-fg-muted" />
          {t("draftStatus.automatedNotice")}
        </p>
      ) : null}
      <DraftReplyEditor email={email} workflow={workflow} />
      <TemplatePicker key={`templates-${email.id}`} email={email} workflow={workflow} />
      <HiddenDetailChips
        key={`hidden-${email.id}`}
        draft={workflow.draft}
        values={values}
        onDraftChange={workflow.setDraft}
        disabled={workflow.isDraftLocked}
      />
      <SourcesChips key={email.id} sources={email.sources} draft={workflow.draft} />
      <TranslateDraft key={`translate-${email.id}`} email={email} workflow={workflow} />
      <RefineInput
        onRefine={workflow.refine}
        disabled={workflow.isDraftLocked}
        isRefining={workflow.isRefining}
      />
      <ScheduleBanner email={email} workflow={workflow} />
      <DraftStatus {...workflow.status} />
      {/* On a phone the send bar is fixed to the bottom, so Send is in reach before scrolling. */}
      <div className="fixed inset-x-0 bottom-0 z-20 flex flex-wrap items-center justify-between gap-x-3 border-t border-line-subtle bg-surface px-4 pb-[env(safe-area-inset-bottom)] pt-1 md:static md:z-auto md:gap-3 md:px-0 md:pb-0 md:pt-4">
        <div className="flex flex-wrap items-center gap-2">
          {/* Approve & Send says the same on a phone, where the fixed bar must stay short. */}
          <p className={`text-xs text-fg-subtle ${email.sentAt ? "" : "hidden md:block"}`}>
            {email.sentAt
              ? t("detail.sentAt", { when: format.timestamp(email.sentAt) })
              : t("detail.notSentYet")}
          </p>
          {email.sentAt ? <UseAsExampleButton key={email.id} emailId={email.id} /> : null}
        </div>
        <DraftActionsBar workflow={workflow} isSent={Boolean(email.sentAt)} />
      </div>
    </section>
  );
}

/** The phone's way back to the list; the phone's own back button does the same. */
function BackToInbox({ onBack }: { onBack: () => void }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      aria-label={t("detail.backToInbox")}
      onClick={onBack}
      className="-ml-2 inline-flex size-11 shrink-0 items-center justify-center rounded-md text-fg-muted hover:bg-surface-muted md:hidden"
    >
      <ArrowLeft aria-hidden className="size-5" />
    </button>
  );
}
