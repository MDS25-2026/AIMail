import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { detailValues, restoreDetails } from "./details";
import { useDetailsHidden } from "./detailsVisibility";
import {
  findRedactionMarkers,
  findTemplatePlaceholders,
  findUnfilledBlanks,
  hasUnsavedEdits,
} from "./draftGuards";
import { useAdaptTemplate, useRefineEmail, useRegenerateEmail, useSendEmail } from "./queries";
import { checkTone } from "./toneCheck";
import type { Email, Tone } from "../types/email";

export enum DraftAction {
  Regenerate = "regenerate",
  Refine = "refine",
  Template = "template",
  Send = "send",
}

/** The last action that failed, and why; DraftStatus turns it into words. */
export type DraftFailure = { action: DraftAction; error: unknown };

export enum ConfirmKind {
  ReplaceEdits = "replaceEdits",
  SendMarkers = "sendMarkers",
  SendTemplates = "sendTemplates",
  ToneWarning = "toneWarning",
}

export type PendingConfirm = { kind: ConfirmKind; markerCount: number };

// What was asked, not a callback: confirming must act on the draft as it is then, including
// anything typed while the question was on screen.
type PendingAction = { kind: ConfirmKind; tone: Tone };

/** What the reader is asked or told about the draft, rendered by DraftStatus. */
export type DraftWorkflowStatus = {
  failure: DraftFailure | null;
  pendingConfirm: PendingConfirm | null;
  onConfirm: () => void;
  onCancel: () => void;
  /** The first draft is still being written; acting now would act on the preview. */
  isGenerating: boolean;
  isLoadFailed: boolean;
  onRetryLoad: () => void;
};

/**
 * What the Changes view compares (#149): the reader's edits to the AI draft, or, until they type,
 * what the last Refine changed.
 */
export type DraftComparison = { before: string; after: string; source: "edits" | "refine" };

/** The detail query the email came from; any query result fits. Absent when there is none. */
export type DetailLoad = { isLoading: boolean; isError: boolean; refetch: () => unknown };

export type DraftWorkflow = {
  draft: string;
  tone: Tone;
  setDraft: (text: string) => void;
  /** A tone change regenerates the draft in that tone. */
  setTone: (tone: Tone) => void;
  regenerate: () => void;
  /** Rejects on failure, so the caller can keep the instruction the reader typed. */
  refine: (instruction: string) => Promise<void>;
  send: () => void;
  /** Draft from template: the agent rewrites a saved template for this email. */
  draftFromTemplate: (templateId: string) => Promise<void>;
  /** Insert: a filled template (placeholders and all) replaces the text in the editor. */
  insertTemplate: (filled: string) => void;
  /** The reader typed something the stored draft does not have; replacing it loses that. */
  hasUnsavedEdits: boolean;
  /** A saved template's {{blanks}} still in the draft; it cannot be sent until they are filled. */
  unfilledBlanks: string[];
  comparison: DraftComparison;
  status: DraftWorkflowStatus;
  announcement: string;
  isRegenerating: boolean;
  isRefining: boolean;
  isTemplating: boolean;
  isSending: boolean;
  /** Anything in flight; the draft must not change under a send, nor a send go out mid-change. */
  isBusy: boolean;
  /** Busy, or already sent: every control that changes the draft is disabled (#172). */
  isDraftLocked: boolean;
  /** Seconds left before an approved send goes out; null outside the undo window. */
  undoCountdown: number | null;
  /** Cancels the send during the undo window; nothing is sent. */
  undoSend: () => void;
};

const NO_DETAIL: DetailLoad = { isLoading: false, isError: false, refetch: () => undefined };

// Every piece of local state remembers which email it belongs to, so a response that lands after
// the reader moved on can neither clear the new email's edits nor show its error there.
type Scoped<T> = { emailId: string; value: T };

function forEmail<T>(scoped: Scoped<T> | null, emailId: string | null): T | null {
  return scoped !== null && scoped.emailId === emailId ? scoped.value : null;
}

function withoutKey<V>(map: ReadonlyMap<string, V>, key: string): ReadonlyMap<string, V> {
  if (!map.has(key)) return map;
  const next = new Map(map);
  next.delete(key);
  return next;
}

/** A mutation is pending for this email: the one in flight was started for it. */
function isPendingFor(
  mutation: { isPending: boolean; variables?: { emailId: string } },
  emailId: string | null,
): boolean {
  return mutation.isPending && mutation.variables?.emailId === emailId;
}

// The failure is already on screen through `failure`; nothing is left to handle.
const shownOnScreen = () => undefined;

/** Duration of the undo window in seconds. */
const UNDO_COUNTDOWN_SECONDS = 5;

/**
 * Regenerate, refine and send for one email, shared by the inbox and the extension panel.
 * Guards the two ways a reader lost work: a regenerate silently replacing their edits, and a
 * redaction marker going out to the recipient unnoticed. Failures stay on screen until the next try.
 */
export function useDraftWorkflow(
  email: Email | null,
  detail: DetailLoad = NO_DETAIL,
): DraftWorkflow {
  const { t } = useTranslation();
  const emailId = email?.id ?? null;
  const [isHidingDetails] = useDetailsHidden();
  // The stored draft holds placeholders; the reader edits it with the real details, and the
  // backend turns them back into placeholders before anything reaches the AI.
  const storedDraft = email?.draftReply ?? "";
  // The detail call no longer drafts; the worker does, and the email says so until it is done.
  const isWaitingForDraft = detail.isLoading || Boolean(email?.isDrafting);
  const serverDraft = isHidingDetails
    ? storedDraft
    : restoreDetails(storedDraft, detailValues(email?.details));

  // Each email keeps its own unsaved edits, so opening another email and coming back loses nothing.
  const [typedByEmail, setTypedByEmail] = useState<ReadonlyMap<string, string>>(new Map());
  // The text each email's last Refine was given; kept in memory only, so a reload drops it.
  const [refinedFrom, setRefinedFrom] = useState<ReadonlyMap<string, string>>(new Map());
  const [chosenTone, setChosenTone] = useState<Scoped<Tone> | null>(null);
  const [failed, setFailed] = useState<Scoped<DraftFailure> | null>(null);
  const [pending, setPending] = useState<Scoped<PendingAction> | null>(null);
  const [announcement, setAnnouncement] = useState("");

  // --- Undo countdown state ---
  // null = not in the undo window; 1–5 = counting down; 0 = expired (send fired)
  const [undoCountdown, setUndoCountdown] = useState<number | null>(null);
  // The email this countdown belongs to, so we clean up on email change.
  const undoEmailIdRef = useRef<string | null>(null);
  const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const regenerateMutation = useRegenerateEmail();
  const refineMutation = useRefineEmail();
  const adaptMutation = useAdaptTemplate();
  const sendMutation = useSendEmail();

  const typedDraft = emailId === null ? null : (typedByEmail.get(emailId) ?? null);
  const draft = typedDraft ?? serverDraft;
  const tone = forEmail(chosenTone, emailId) ?? email?.tone ?? "professional";
  const pendingAction = forEmail(pending, emailId);

  // Clear, then set on the next frame: the same text twice is no DOM change, so a second
  // "Draft regenerated" would never be read out.
  const announce = (text: string) => {
    setAnnouncement("");
    requestAnimationFrame(() => setAnnouncement(text));
  };

  // Clear the countdown interval and reset state.
  const clearCountdown = () => {
    if (countdownIntervalRef.current !== null) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
    setUndoCountdown(null);
    undoEmailIdRef.current = null;
  };

  // Cancel any active countdown when the email changes or on unmount.
  useEffect(() => {
    return () => {
      clearCountdown();
    };
  }, []);

  useEffect(() => {
    if (emailId !== undoEmailIdRef.current && undoEmailIdRef.current !== null) {
      clearCountdown();
    }
  }, [emailId]);

  // Last issued wins: two regenerates for the same email share one cache entry, so a slow first
  // response could otherwise overwrite a newer one.
  const requestSeqRef = useRef(0);
  const runMutation = async (
    id: string,
    action: DraftAction,
    run: () => Promise<unknown>,
    done: string,
    onDone?: () => void,
  ) => {
    const seq = ++requestSeqRef.current;
    setFailed(null);
    try {
      await run();
    } catch (error) {
      if (seq === requestSeqRef.current) setFailed({ emailId: id, value: { action, error } });
      throw error;
    }
    if (seq !== requestSeqRef.current) return;
    setTypedByEmail((current) => withoutKey(current, id));
    // Any newer draft ends the Refine comparison; a Refine then records its own.
    setRefinedFrom((current) => withoutKey(current, id));
    onDone?.();
    announce(done);
  };

  const startRegenerate = (id: string, nextTone: Tone) => {
    setChosenTone({ emailId: id, value: nextTone });
    const request = () => regenerateMutation.mutateAsync({ emailId: id, tone: nextTone });
    runMutation(id, DraftAction.Regenerate, request, t("announce.regenerated")).catch(() => {
      // The draft did not change, so the toggle goes back to the tone the stored draft is in, unless the
      // reader has picked another tone since.
      setChosenTone((current) =>
        current?.emailId === id && current.value === nextTone ? null : current,
      );
    });
  };

  const startSend = (id: string) => {
    const request = () => sendMutation.mutateAsync({ emailId: id, draft });
    runMutation(id, DraftAction.Send, request, t("announce.sent")).catch(shownOnScreen);
  };

  // Busy only for the email the action belongs to: a send on one email doesn't lock another.
  const isRegenerating = isPendingFor(regenerateMutation, emailId);
  const isRefining = isPendingFor(refineMutation, emailId);
  const isTemplating = isPendingFor(adaptMutation, emailId);
  const isSending = isPendingFor(sendMutation, emailId);
  const isCountingDown = undoCountdown !== null && undoCountdown > 0;
  // Locking: during mutations, pregen, or active undo countdown, prevent editing/sending race conditions:
  const isBusy =
    isRegenerating ||
    isRefining ||
    isTemplating ||
    isSending ||
    isWaitingForDraft ||
    isCountingDown;
  // The panels disable every control that changes the draft; this backs them up. A sent reply is
  // final, and a change mid-send would leave the screen showing text other than what went out.
  const isDraftLocked = isBusy || Boolean(email?.sentAt);

  /**
   * Begins the 5-second undo countdown for the given email. When it expires the actual
   * send mutation fires. Call `undoSend()` to cancel during the window.
   */
  const beginUndoCountdown = (id: string) => {
    clearCountdown();
    undoEmailIdRef.current = id;
    setUndoCountdown(UNDO_COUNTDOWN_SECONDS);

    let remaining = UNDO_COUNTDOWN_SECONDS;
    countdownIntervalRef.current = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clearInterval(countdownIntervalRef.current!);
        countdownIntervalRef.current = null;
        setUndoCountdown(0);
        // Fire the actual send — use id captured in closure so we send the right email.
        startSend(id);
      } else {
        setUndoCountdown(remaining);
      }
    }, 1000);
  };

  /** Cancels the undo countdown. No email is sent. */
  const undoSend = () => {
    clearCountdown();
  };

  const regenerate = (nextTone: Tone = tone) => {
    if (emailId === null || isDraftLocked) return;
    if (hasUnsavedEdits(typedDraft, serverDraft)) {
      setPending({ emailId, value: { kind: ConfirmKind.ReplaceEdits, tone: nextTone } });
      return;
    }
    startRegenerate(emailId, nextTone);
  };

  const refine = async (instruction: string) => {
    if (emailId === null || isDraftLocked) return;
    const id = emailId;
    // The chosen tone goes too, so the revision and its review keep it.
    const request = () => refineMutation.mutateAsync({ emailId: id, instruction, draft, tone });
    const recordBefore = () => setRefinedFrom((current) => new Map(current).set(id, draft));
    await runMutation(id, DraftAction.Refine, request, t("announce.refined"), recordBefore);
  };

  const draftFromTemplate = async (templateId: string) => {
    if (emailId === null || isDraftLocked) return;
    const id = emailId;
    const request = () => adaptMutation.mutateAsync({ templateId, emailId: id, tone });
    await runMutation(id, DraftAction.Template, request, t("announce.templateDrafted"));
  };

  const refineBefore = emailId === null ? undefined : refinedFrom.get(emailId);
  const comparison: DraftComparison =
    typedDraft === null && refineBefore !== undefined
      ? { before: refineBefore, after: draft, source: "refine" }
      : { before: serverDraft, after: draft, source: "edits" };

  // Each warning in order; "send anyway" on one resumes after it, so every send still gets the later
  // checks and the undo window.
  const sendGuards: { kind: ConfirmKind; isTriggered: (text: string) => boolean }[] = [
    { kind: ConfirmKind.SendMarkers, isTriggered: (text) => findRedactionMarkers(text).length > 0 },
    {
      kind: ConfirmKind.SendTemplates,
      isTriggered: (text) => findTemplatePlaceholders(text).length > 0,
    },
    { kind: ConfirmKind.ToneWarning, isTriggered: (text) => checkTone(text).hasIssues },
  ];

  const continueSend = (id: string, fromGuard: number) => {
    const triggered = sendGuards.slice(fromGuard).find((guard) => guard.isTriggered(draft));
    if (triggered) {
      setPending({ emailId: id, value: { kind: triggered.kind, tone } });
      return;
    }
    beginUndoCountdown(id);
  };

  const unfilledBlanks = findUnfilledBlanks(draft);

  const send = () => {
    if (emailId === null || isDraftLocked || unfilledBlanks.length > 0) return;
    continueSend(emailId, 0);
  };

  const confirm = () => {
    setPending(null);
    if (emailId === null || pendingAction === null) return;
    if (pendingAction.kind === ConfirmKind.ReplaceEdits) {
      startRegenerate(emailId, pendingAction.tone);
      return;
    }
    // "Send anyway": the checks after this one still run, then the undo countdown.
    const confirmed = sendGuards.findIndex((guard) => guard.kind === pendingAction.kind);
    continueSend(emailId, confirmed + 1);
  };

  const status: DraftWorkflowStatus = {
    failure: forEmail(failed, emailId),
    pendingConfirm: pendingAction && {
      kind: pendingAction.kind,
      markerCount:
        pendingAction.kind === ConfirmKind.SendTemplates
          ? findTemplatePlaceholders(draft).length
          : findRedactionMarkers(draft).length,
    },
    onConfirm: confirm,
    onCancel: () => setPending(null),
    isGenerating: isWaitingForDraft,
    isLoadFailed: detail.isError,
    onRetryLoad: () => void detail.refetch(),
  };

  const setDraft = (text: string) => {
    if (emailId === null) return;
    setTypedByEmail((current) => new Map(current).set(emailId, text));
    // The warning is moot once every marker has been typed over.
    const isMarkerWarning = pendingAction?.kind === ConfirmKind.SendMarkers;
    if (isMarkerWarning && findRedactionMarkers(text).length === 0) setPending(null);
  };

  // Shown the way the editor shows the stored draft: real details, unless the reader hid them.
  const insertTemplate = (filled: string) =>
    setDraft(isHidingDetails ? filled : restoreDetails(filled, detailValues(email?.details)));

  return {
    draft,
    tone,
    setDraft,
    draftFromTemplate,
    insertTemplate,
    hasUnsavedEdits: hasUnsavedEdits(typedDraft, serverDraft),
    unfilledBlanks,
    setTone: regenerate,
    regenerate: () => regenerate(),
    refine,
    send,
    undoSend,
    undoCountdown,
    comparison,
    status,
    announcement,
    isRegenerating,
    isRefining,
    isTemplating,
    isSending,
    isBusy,
    isDraftLocked,
  };
}
