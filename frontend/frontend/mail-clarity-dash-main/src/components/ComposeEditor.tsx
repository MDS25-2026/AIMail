import { ArrowLeft, CircleAlert, CircleCheck, LoaderCircle, Sparkles } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { useTranslation } from "react-i18next";

import { composeErrorMessage } from "../lib/composeErrors";
import { DetailsContext } from "../lib/detailsContext";
import {
  ComposeAction,
  SaveStatus,
  useComposeDraft,
  type ComposeWorkflow,
} from "../lib/useComposeDraft";
import { cn } from "../lib/utils";
import { ComposeState, type ComposeDraft } from "../types/compose";
import ComposeOutcomeNotice from "./ComposeOutcomeNotice";
import ComposeSendBar from "./ComposeSendBar";
import ComposeSentView from "./ComposeSentView";
import ConfirmAction from "./ConfirmAction";
import CriticConfidenceBadge from "./CriticConfidenceBadge";
import DetailsToggle from "./DetailsToggle";
import DraftStatus from "./DraftStatus";
import PrivacyReceipt from "./PrivacyReceipt";
import RecipientsInput from "./RecipientsInput";
import RefineInput from "./RefineInput";
import ReviewReasonList from "./ReviewReasonList";
import SourcesChips from "./SourcesChips";
import ToneToggle from "./ToneToggle";
import { button, field } from "./variants";

// backend/app/compose.py MAX_SUBJECT_CHARS and MAX_BRIEF_CHARS; longer is refused unsaved.
const SUBJECT_MAX_CHARS = 300;
const BRIEF_MAX_CHARS = 4_000;

// What to say when the backend names no reason; each action leaves the email as it was.
const FALLBACK_BY_ACTION = {
  [ComposeAction.Write]: "compose.failed.write",
  [ComposeAction.Refine]: "compose.failed.refine",
  [ComposeAction.Send]: "compose.failed.send",
  [ComposeAction.Settle]: "compose.failed.settle",
  [ComposeAction.Delete]: "compose.failed.delete",
} as const;

type ComposeEditorProps = { draft: ComposeDraft; onBack: () => void; onDeleted: () => void };

/** One new email: recipients, subject, the brief AIMail writes from, the body, and sending. */
export default function ComposeEditor({ draft, onBack, onDeleted }: ComposeEditorProps) {
  const compose = useComposeDraft(draft, onDeleted);
  return (
    <DetailsContext.Provider value={compose.values}>
      <div className="relative h-full overflow-y-auto">
        {/* Read out when a slow action finishes, since the result appears elsewhere. */}
        <p role="status" aria-live="polite" className="sr-only">
          {compose.announcement}
        </p>
        <ComposeHeader draft={draft} compose={compose} onBack={onBack} />
        <div className="space-y-4 p-4 md:p-6">
          {draft.state === ComposeState.OutcomeUnknown ? (
            <ComposeOutcomeNotice compose={compose} />
          ) : null}
          {draft.state === ComposeState.Sent ? (
            <ComposeSentView draft={draft} />
          ) : (
            <ComposeForm draft={draft} compose={compose} />
          )}
        </div>
      </div>
    </DetailsContext.Provider>
  );
}

type SectionProps = { draft: ComposeDraft; compose: ComposeWorkflow };

function ComposeHeader({ draft, compose, onBack }: SectionProps & { onBack: () => void }) {
  const { t } = useTranslation();
  const subject = compose.fields.subject.trim();
  return (
    <header className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-line bg-surface px-4 py-3 md:px-6">
      <button
        type="button"
        aria-label={t("compose.back")}
        onClick={onBack}
        className="-ml-2 inline-flex size-11 shrink-0 items-center justify-center rounded-md text-fg-muted hover:bg-surface-muted md:hidden"
      >
        <ArrowLeft aria-hidden className="size-5" />
      </button>
      <h2 className="min-w-0 flex-1 truncate text-base font-semibold text-fg">
        {subject || t("compose.newTitle")}
      </h2>
      {draft.state === ComposeState.Draft ? <SaveStatusText status={compose.saveStatus} /> : null}
      <PrivacyReceipt
        email={{
          subject: draft.subject,
          // The brief and the body both go to the model: one to write from, one to check and refine.
          body: [draft.brief, draft.body].filter(Boolean).join("\n\n"),
          details: draft.details,
          egress: draft.egress,
        }}
      />
      {draft.details?.length ? <DetailsToggle /> : null}
      <DeleteDraft draft={draft} compose={compose} />
    </header>
  );
}

const SAVE_TEXT = {
  [SaveStatus.Idle]: null,
  [SaveStatus.Saving]: "compose.save.saving",
  [SaveStatus.Saved]: "compose.save.saved",
  [SaveStatus.Failed]: "compose.save.failed",
} as const;

/** Always rendered, so a screen reader hears each change of the live region. */
function SaveStatusText({ status }: { status: SaveStatus }) {
  const { t } = useTranslation();
  const key = SAVE_TEXT[status];
  const isFailed = status === SaveStatus.Failed;
  return (
    <p
      role="status"
      className={cn("flex items-center gap-1 text-xs", isFailed ? "text-danger" : "text-fg-muted")}
    >
      {status === SaveStatus.Saved ? <CircleCheck aria-hidden className="size-3.5" /> : null}
      {isFailed ? <CircleAlert aria-hidden className="size-3.5" /> : null}
      {key ? t(key) : null}
    </p>
  );
}

/** Drafts and sent emails can go; one being sent, or maybe sent, is settled first. */
function DeleteDraft({ draft, compose }: SectionProps) {
  const { t } = useTranslation();
  const isSent = draft.state === ComposeState.Sent;
  // Not mid-send either: a draft deleted in its undo window would still be sent.
  const isBusyElsewhere =
    compose.undoCountdown !== null ||
    (compose.busy !== null && compose.busy !== ComposeAction.Delete);
  if ((draft.state !== ComposeState.Draft && !isSent) || isBusyElsewhere) return null;
  const failure = compose.failure?.action === ComposeAction.Delete ? compose.failure : null;
  return (
    <ConfirmAction
      trigger={t("compose.delete")}
      triggerName={t(isSent ? "compose.deleteSentName" : "compose.deleteName")}
      question={t(isSent ? "compose.deleteSentQuestion" : "compose.deleteQuestion")}
      confirm={t("compose.delete")}
      pending={t("compose.deleting")}
      cancel={t("compose.cancel")}
      onConfirm={compose.remove}
      isPending={compose.busy === ComposeAction.Delete}
      error={
        failure ? composeErrorMessage(failure.error, t, FALLBACK_BY_ACTION[failure.action]) : null
      }
    />
  );
}

function ComposeForm({ draft, compose }: SectionProps) {
  const { t } = useTranslation();
  const { fields, setField, isLocked } = compose;
  const ids = { to: useId(), cc: useId(), subject: useId(), brief: useId(), body: useId() };
  const [isCcOpen, setIsCcOpen] = useState(fields.cc.length > 0);
  const toRef = useRef<HTMLInputElement>(null);
  const ccRef = useRef<HTMLInputElement>(null);
  // A brand-new email starts where the user types first; an opened draft keeps the page's focus.
  const isNewRef = useRef(!fields.to.length && !fields.subject && !fields.brief && !fields.body);
  useEffect(() => {
    if (isNewRef.current) toRef.current?.focus();
  }, []);

  // Hidden again only while empty: a Cc nobody can see would still be sent.
  const canHideCc = fields.cc.length === 0;
  const toggleCc = () => {
    if (isCcOpen) {
      setIsCcOpen(false);
      return;
    }
    flushSync(() => setIsCcOpen(true));
    ccRef.current?.focus();
  };
  const ccPanelId = `${ids.cc}-panel`;

  return (
    <div className="space-y-4">
      <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
        <RecipientsInput
          id={ids.to}
          label={t("compose.to")}
          recipients={fields.to}
          otherCount={fields.cc.length}
          onChange={(to) => setField("to", to)}
          disabled={isLocked}
          inputRef={toRef}
        />
        <button
          type="button"
          aria-expanded={isCcOpen}
          aria-controls={ccPanelId}
          disabled={isLocked || (isCcOpen && !canHideCc)}
          onClick={toggleCc}
          className={button({ intent: "quiet", size: "xs" })}
        >
          {t(isCcOpen ? "compose.hideCc" : "compose.addCc")}
        </button>
        <div id={ccPanelId} hidden={!isCcOpen}>
          {isCcOpen ? (
            <RecipientsInput
              id={ids.cc}
              label={t("compose.cc")}
              recipients={fields.cc}
              otherCount={fields.to.length}
              onChange={(cc) => setField("cc", cc)}
              disabled={isLocked}
              inputRef={ccRef}
            />
          ) : null}
        </div>
        <div>
          <label htmlFor={ids.subject} className="text-xs font-semibold text-fg-muted">
            {t("compose.subject")}
          </label>
          <input
            id={ids.subject}
            type="text"
            value={fields.subject}
            maxLength={SUBJECT_MAX_CHARS}
            disabled={isLocked}
            placeholder={t("compose.subjectPlaceholder")}
            onChange={(event) => setField("subject", event.target.value)}
            className={cn(field(), "mt-1 w-full")}
          />
        </div>
      </section>
      <BriefSection draft={draft} compose={compose} briefId={ids.brief} />
      <BodySection draft={draft} compose={compose} bodyId={ids.body} />
      <DraftStatus {...compose.status} />
      <ComposeFailure compose={compose} />
      <ComposeSendBar compose={compose} />
    </div>
  );
}

function BriefSection({ draft, compose, briefId }: SectionProps & { briefId: string }) {
  const { t } = useTranslation();
  const { fields, isLocked } = compose;
  const isWriting = compose.busy === ComposeAction.Write;
  const needsBrief = fields.brief.trim() === "";
  const hintId = `${briefId}-hint`;
  const reasonId = `${briefId}-reason`;
  const writeLabel = draft.generatedAt ? "compose.rewrite" : "compose.write";
  return (
    <section className="space-y-2 rounded-lg border border-line bg-surface p-4">
      <label htmlFor={briefId} className="text-sm font-semibold text-fg">
        {t("compose.brief")}
      </label>
      <p id={hintId} className="text-xs text-fg-muted">
        {t("compose.briefHint")}
      </p>
      <textarea
        id={briefId}
        value={fields.brief}
        rows={3}
        maxLength={BRIEF_MAX_CHARS}
        disabled={isLocked}
        aria-describedby={hintId}
        placeholder={t("compose.briefPlaceholder")}
        onChange={(event) => compose.setField("brief", event.target.value)}
        className={cn(field(), "w-full resize-y leading-relaxed")}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <ToneToggle
          tone={fields.tone}
          onToneChange={(tone) => compose.setField("tone", tone)}
          disabled={isLocked}
        />
        <button
          type="button"
          disabled={isLocked || needsBrief}
          aria-describedby={needsBrief ? reasonId : undefined}
          onClick={compose.write}
          className={cn(button({ intent: "primary", size: "md" }), "gap-1.5")}
        >
          <Sparkles aria-hidden className="size-4" />
          {isWriting ? t("compose.writing") : t(writeLabel)}
        </button>
      </div>
      {needsBrief ? (
        <p id={reasonId} className="text-right text-xs text-fg-muted">
          {t("compose.needsBrief")}
        </p>
      ) : null}
      {isWriting ? (
        <p role="status" className="flex items-center gap-2 text-sm text-fg-muted">
          <LoaderCircle
            aria-hidden
            className="size-4 shrink-0 animate-spin motion-reduce:animate-none"
          />
          {t("compose.writingStatus")}
        </p>
      ) : null}
    </section>
  );
}

function BodySection({ draft, compose, bodyId }: SectionProps & { bodyId: string }) {
  const { t } = useTranslation();
  const { fields, isLocked } = compose;
  const hasBody = fields.body.trim() !== "";
  const reasons = draft.reviewReasons ?? [];
  const isChecked = hasBody && draft.generatedAt && typeof draft.criticConfidence === "number";
  return (
    <section className="space-y-2 rounded-lg border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <label htmlFor={bodyId} className="text-sm font-semibold text-fg">
          {t("compose.body")}
        </label>
        {isChecked ? (
          <CriticConfidenceBadge
            value={draft.criticConfidence ?? 0}
            isFlagged={reasons.length > 0}
          />
        ) : null}
      </div>
      {hasBody ? <ReviewReasonList reasons={reasons} /> : null}
      <textarea
        id={bodyId}
        value={fields.body}
        rows={12}
        disabled={isLocked}
        placeholder={t("compose.bodyPlaceholder")}
        onChange={(event) => compose.setField("body", event.target.value)}
        className={cn(field(), "w-full resize-y p-3 leading-relaxed")}
      />
      <SourcesChips sources={draft.sources ?? []} draft={fields.body} />
      {hasBody ? (
        <RefineInput
          onRefine={compose.refine}
          disabled={isLocked}
          isRefining={compose.busy === ComposeAction.Refine}
          placeholder={t("compose.refinePlaceholder")}
        />
      ) : null}
    </section>
  );
}

function ComposeFailure({ compose }: { compose: ComposeWorkflow }) {
  const { t } = useTranslation();
  const failure = compose.failure;
  // A failed delete is shown in the delete question itself.
  if (!failure || failure.action === ComposeAction.Delete) return null;
  return (
    <p
      role="alert"
      className="flex gap-2 rounded-md border border-danger-line bg-danger-soft p-3 text-sm text-danger"
    >
      <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
      {composeErrorMessage(failure.error, t, FALLBACK_BY_ACTION[failure.action])}
    </p>
  );
}
