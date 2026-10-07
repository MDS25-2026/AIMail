import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  DraftRefusedError,
  GoogleAccessExpiredError,
  SendNotGrantedError,
  SendOutcomeUnknownError,
  UnresolvedPlaceholdersError,
} from "./api";
import { detailValues, restoreDetails } from "./details";
import { useDetailsHidden } from "./detailsVisibility";
import { findRedactionMarkers, findTemplatePlaceholders, hasUnsavedEdits } from "./draftGuards";
import { useRefineEmail, useRegenerateEmail, useSendEmail } from "./queries";
import type { Email, Tone } from "../types/email";

export enum DraftAction {
  Regenerate = "regenerate",
  Refine = "refine",
  Send = "send",
}

/** Why the last action failed; each value is a `draftStatus.failed.*` message. */
export enum DraftFailure {
  Regenerate = "regenerate",
  Refine = "refine",
  Send = "send",
  Refused = "refused",
  SendUnknown = "sendUnknown",
  SendNotGranted = "sendNotGranted",
  AccessExpired = "accessExpired",
  Unresolved = "unresolved",
}

const FAILURE_BY_ACTION: Record<DraftAction, DraftFailure> = {
  [DraftAction.Regenerate]: DraftFailure.Regenerate,
  [DraftAction.Refine]: DraftFailure.Refine,
  [DraftAction.Send]: DraftFailure.Send,
};

function failureFor(error: unknown, action: DraftAction): DraftFailure {
  if (error instanceof DraftRefusedError) return DraftFailure.Refused;
  if (error instanceof SendOutcomeUnknownError) return DraftFailure.SendUnknown;
  if (error instanceof SendNotGrantedError) return DraftFailure.SendNotGranted;
  if (error instanceof GoogleAccessExpiredError) return DraftFailure.AccessExpired;
  if (error instanceof UnresolvedPlaceholdersError) return DraftFailure.Unresolved;
  return FAILURE_BY_ACTION[action];
}

export enum ConfirmKind {
  ReplaceEdits = "replaceEdits",
  SendMarkers = "sendMarkers",
  SendTemplates = "sendTemplates",
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
};

// Every piece of local state remembers which email it belongs to, so a response that lands after
// the reader moved on can neither clear the new email's edits nor show its error there.
type Scoped<T> = { emailId: string; value: T };

function forEmail<T>(scoped: Scoped<T> | null, emailId: string | null): T | null {
  return scoped !== null && scoped.emailId === emailId ? scoped.value : null;
}

// The failure is already on screen through `failure`; nothing is left to handle.
const shownOnScreen = () => undefined;

/**
 * Regenerate, refine and send for one email, shared by the inbox and the extension panel.
 * Guards the two ways a reader lost work: a regenerate silently replacing their edits, and a
 * redaction marker going out to the recipient unnoticed. Failures stay on screen until the next try.
 */
export function useDraftWorkflow(email: Email | null) {
  const { t } = useTranslation();
  const emailId = email?.id ?? null;
  const [isHidingDetails] = useDetailsHidden();
  // The stored draft holds placeholders; the reader edits it with the real details, and the
  // backend turns them back into placeholders before anything reaches the AI.
  const storedDraft = email?.draftReply ?? "";
  const serverDraft = isHidingDetails
    ? storedDraft
    : restoreDetails(storedDraft, detailValues(email?.details));

  const [typed, setTyped] = useState<Scoped<string> | null>(null);
  const [chosenTone, setChosenTone] = useState<Scoped<Tone> | null>(null);
  const [failed, setFailed] = useState<Scoped<DraftFailure> | null>(null);
  const [pending, setPending] = useState<Scoped<PendingAction> | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const regenerateMutation = useRegenerateEmail();
  const refineMutation = useRefineEmail();
  const sendMutation = useSendEmail();

  const typedDraft = forEmail(typed, emailId);
  const draft = typedDraft ?? serverDraft;
  const tone = forEmail(chosenTone, emailId) ?? email?.tone ?? "professional";
  const pendingAction = forEmail(pending, emailId);

  // Clear, then set on the next frame: the same text twice is no DOM change, so a second
  // "Draft regenerated" would never be read out.
  const announce = (text: string) => {
    setAnnouncement("");
    requestAnimationFrame(() => setAnnouncement(text));
  };

  // Last issued wins: two regenerates for the same email share one cache entry, so a slow first
  // response could otherwise overwrite a newer one.
  const requestSeqRef = useRef(0);
  const runMutation = async (
    id: string,
    action: DraftAction,
    run: () => Promise<unknown>,
    done: string,
  ) => {
    const seq = ++requestSeqRef.current;
    setFailed(null);
    try {
      await run();
    } catch (error) {
      const failure = failureFor(error, action);
      if (seq === requestSeqRef.current) setFailed({ emailId: id, value: failure });
      throw error;
    }
    if (seq !== requestSeqRef.current) return;
    setTyped((current) => (current?.emailId === id ? null : current));
    announce(done);
  };

  const startRegenerate = (id: string, nextTone: Tone) => {
    setChosenTone({ emailId: id, value: nextTone });
    const request = () => regenerateMutation.mutateAsync({ emailId: id, tone: nextTone });
    runMutation(id, DraftAction.Regenerate, request, t("announce.regenerated")).catch(
      shownOnScreen,
    );
  };

  const startSend = (id: string) => {
    const request = () => sendMutation.mutateAsync({ emailId: id, draft });
    runMutation(id, DraftAction.Send, request, t("announce.sent")).catch(shownOnScreen);
  };

  const regenerate = (nextTone: Tone = tone) => {
    if (emailId === null) return;
    if (hasUnsavedEdits(typedDraft, serverDraft)) {
      setPending({ emailId, value: { kind: ConfirmKind.ReplaceEdits, tone: nextTone } });
      return;
    }
    startRegenerate(emailId, nextTone);
  };

  /** Rejects on failure, so the caller can keep the instruction the reader typed. */
  const refine = async (instruction: string) => {
    if (emailId === null) return;
    const id = emailId;
    const request = () => refineMutation.mutateAsync({ emailId: id, instruction, draft });
    await runMutation(id, DraftAction.Refine, request, t("announce.refined"));
  };

  const send = () => {
    if (emailId === null) return;
    if (findRedactionMarkers(draft).length > 0) {
      setPending({ emailId, value: { kind: ConfirmKind.SendMarkers, tone } });
      return;
    }
    if (findTemplatePlaceholders(draft).length > 0) {
      setPending({ emailId, value: { kind: ConfirmKind.SendTemplates, tone } });
      return;
    }
    startSend(emailId);
  };

  const confirm = () => {
    setPending(null);
    if (emailId === null || pendingAction === null) return;
    if (pendingAction.kind === ConfirmKind.ReplaceEdits) {
      startRegenerate(emailId, pendingAction.tone);
      return;
    }
    startSend(emailId);
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
  };

  return {
    draft,
    tone,
    setDraft: (text: string) => {
      if (emailId === null) return;
      setTyped({ emailId, value: text });
      // The warning is moot once every marker has been typed over.
      const isMarkerWarning = pendingAction?.kind === ConfirmKind.SendMarkers;
      if (isMarkerWarning && findRedactionMarkers(text).length === 0) setPending(null);
    },
    regenerate,
    refine,
    send,
    status,
    announcement,
    isRegenerating: regenerateMutation.isPending,
    isRefining: refineMutation.isPending,
    isSending: sendMutation.isPending,
  };
}
