import type { TFunction } from "i18next";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  ComposeState,
  type ComposeDraft,
  type ComposeFields,
  type ComposeSendFailure,
  type OutgoingEmail,
  type SettleOutcome,
} from "../types/compose";
import { detailValues, hasMissingDetails, restoreDetails, type DetailValues } from "./details";
import { useDetailsHidden } from "./detailsVisibility";
import { findRedactionMarkers, findTemplatePlaceholders, findUnfilledBlanks } from "./draftGuards";
import {
  useComposeSendFailure,
  useDeleteComposeDraft,
  useRefineComposeDraft,
  useSaveComposeDraft,
  useSendComposeDraft,
  useSettleComposeOutcome,
  useWriteComposeDraft,
} from "./queries";
import { checkTone } from "./toneCheck";
import { ConfirmKind, type DraftWorkflowStatus } from "./useDraftWorkflow";
import { useUndoCountdown } from "./useUndoCountdown";

export enum ComposeAction {
  Write = "write",
  Refine = "refine",
  Send = "send",
  Settle = "settle",
  Delete = "delete",
}

export type ComposeFailure = { action: ComposeAction; error: unknown };

export enum SaveStatus {
  Idle = "idle",
  Saving = "saving",
  Saved = "saved",
  Failed = "failed",
}

/** Why the email cannot go yet; the backend refuses each of these too. */
export enum SendBlocker {
  NoRecipient = "noRecipient",
  NoSubject = "noSubject",
  NoBody = "noBody",
  MissingDetails = "missingDetails",
  UnfilledBlanks = "unfilledBlanks",
  RedactionMarkers = "redactionMarkers",
}

/** Saved this long after the last keystroke: one save per pause in typing, not one per key. */
export const AUTOSAVE_MS = 800;

// The reply's warnings that the backend lets through, in the reply's order; "send anyway" on one
// resumes after it. A redaction marker is a blocker instead: compose's send always refuses it.
const SEND_GUARDS: { kind: ConfirmKind; isTriggered: (text: string) => boolean }[] = [
  {
    kind: ConfirmKind.SendTemplates,
    isTriggered: (text) => findTemplatePlaceholders(text).length > 0,
  },
  { kind: ConfirmKind.ToneWarning, isTriggered: (text) => checkTone(text).hasIssues },
];

const outgoingText = (fields: ComposeFields) => `${fields.subject}\n${fields.body}`;

export function sendBlockers(fields: ComposeFields, values: DetailValues): SendBlocker[] {
  const checks: [SendBlocker, boolean][] = [
    [SendBlocker.NoRecipient, fields.to.length === 0],
    [SendBlocker.NoSubject, fields.subject.trim() === ""],
    [SendBlocker.NoBody, fields.body.trim() === ""],
    [SendBlocker.MissingDetails, hasMissingDetails(outgoingText(fields), values)],
    [SendBlocker.UnfilledBlanks, findUnfilledBlanks(fields.body).length > 0],
    [SendBlocker.RedactionMarkers, findRedactionMarkers(outgoingText(fields)).length > 0],
  ];
  return checks.filter(([, isBlocking]) => isBlocking).map(([blocker]) => blocker);
}

/** A new email's own wording for the reply's questions. */
function confirmText(kind: ConfirmKind, templateGaps: number, t: TFunction): string {
  if (kind === ConfirmKind.ReplaceEdits) return t("compose.confirm.replaceEdits");
  if (kind === ConfirmKind.ToneWarning) return t("compose.confirm.toneWarning");
  return t("compose.confirm.sendTemplates", { count: templateGaps });
}

/** A send that failed since this editor's last action, while the email is a draft again. */
function keptFailure(
  kept: ComposeSendFailure | null | undefined,
  answered: ComposeSendFailure | null,
  state: ComposeState,
): ComposeFailure | null {
  if (!kept || kept === answered || state !== ComposeState.Draft) return null;
  return { action: ComposeAction.Send, error: kept.error };
}

type Edits = Partial<ComposeFields>;

function withoutText(edits: Edits, ...keys: (keyof ComposeFields)[]): Edits {
  return Object.fromEntries(Object.entries(edits).filter(([key]) => !keys.some((k) => k === key)));
}

const hasChanges = (edits: Edits) => Object.keys(edits).length > 0;

// The failure is already on screen through `failure`; nothing is left to handle.
const shownOnScreen = () => undefined;

export type ComposeWorkflow = {
  fields: ComposeFields;
  /** Ignored while the email is locked; saved AUTOSAVE_MS after the last change. */
  setField: <K extends keyof ComposeFields>(key: K, value: ComposeFields[K]) => void;
  values: DetailValues;
  saveStatus: SaveStatus;
  write: () => void;
  /** Rejects on failure, so RefineInput can keep the instruction typed. */
  refine: (instruction: string) => Promise<void>;
  send: () => void;
  undoSend: () => void;
  /** Seconds left before the approved send goes out; null outside the undo window. */
  undoCountdown: number | null;
  remindIfNoReply: boolean;
  setRemindIfNoReply: (isOn: boolean) => void;
  settle: (outcome: SettleOutcome) => void;
  /** Rejects on failure, so the delete question stays open with its error. */
  remove: () => Promise<void>;
  blockers: SendBlocker[];
  /** The send warnings, in the shape the reply's DraftStatus shows them. */
  status: DraftWorkflowStatus;
  failure: ComposeFailure | null;
  busy: ComposeAction | null;
  /** Busy, counting down, sending or sent: nothing may change the email. */
  isLocked: boolean;
  isSending: boolean;
  announcement: string;
};

/**
 * One new email: fields shown with their real details (unless hidden), saved as the user types,
 * written and refined by the model, and sent after the undo window, exactly as approved.
 */
export function useComposeDraft(draft: ComposeDraft, onDeleted: () => void): ComposeWorkflow {
  const { t } = useTranslation();
  const id = draft.id;
  const [isHidingDetails] = useDetailsHidden();
  const values = useMemo(() => detailValues(draft.details), [draft.details]);
  const shown = (text: string) => (isHidingDetails ? text : restoreDetails(text, values));
  // The body exactly as the AI returned it in this editor, placeholders and all. Only that may be
  // rewritten without asking: after a reload, a saved body may be the user's own text.
  const aiBodyRef = useRef<string | null>(null);

  // What the user typed over the stored draft, field by field, as the reply editor keeps edits.
  const [edits, setEdits] = useState<Edits>({});
  const fields: ComposeFields = {
    to: draft.to,
    cc: draft.cc,
    subject: shown(draft.subject),
    brief: shown(draft.brief),
    body: shown(draft.body),
    tone: draft.tone,
    ...edits,
  };

  const [busy, setBusy] = useState<ComposeAction | null>(null);
  const [failure, setFailure] = useState<ComposeFailure | null>(null);
  const keptSendFailure = useComposeSendFailure(id).data;
  // The kept failure there was when this editor last acted: that one is answered, a newer is not.
  const [answeredFailure, setAnsweredFailure] = useState<ComposeSendFailure | null>(null);
  const [pending, setPending] = useState<ConfirmKind | null>(null);
  const [remindIfNoReply, setRemindIfNoReply] = useState(false);
  const [saveStatus, setSaveStatus] = useState(SaveStatus.Idle);
  const [announcement, setAnnouncement] = useState("");
  const countdown = useUndoCountdown();

  const { mutateAsync: saveDraft } = useSaveComposeDraft();
  const { mutateAsync: writeDraft } = useWriteComposeDraft();
  const { mutateAsync: refineDraft } = useRefineComposeDraft();
  const { mutateAsync: sendDraft } = useSendComposeDraft();
  const { mutateAsync: settleOutcome } = useSettleComposeOutcome();
  const { mutateAsync: deleteDraft } = useDeleteComposeDraft();

  const unsavedRef = useRef<Edits>({});
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Saves run one after another, and every action waits for them: a save landing after a write
  // would put the old body back.
  const savingRef = useRef<Promise<void>>(Promise.resolve());

  const saveNow = useCallback((): Promise<void> => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = null;
    const changes = unsavedRef.current;
    if (!hasChanges(changes)) return savingRef.current;
    unsavedRef.current = {};
    setSaveStatus(SaveStatus.Saving);
    savingRef.current = savingRef.current
      .then(() => saveDraft({ id, fields: changes }))
      .then(
        () => setSaveStatus(SaveStatus.Saved),
        () => {
          // Kept for the next save; anything typed since is newer and wins.
          unsavedRef.current = { ...changes, ...unsavedRef.current };
          setSaveStatus(SaveStatus.Failed);
        },
      );
    return savingRef.current;
  }, [id, saveDraft]);

  // Leaving the draft saves what was typed at once rather than dropping it.
  useEffect(() => () => void saveNow(), [saveNow]);

  const isCountingDown = countdown.secondsLeft !== null;
  const isLocked = draft.state !== ComposeState.Draft || busy !== null || isCountingDown;

  // Clear, then set on the next frame: the same text twice is no DOM change, so it would not be read.
  const announce = (text: string) => {
    setAnnouncement("");
    requestAnimationFrame(() => setAnnouncement(text));
  };

  const run = async (action: ComposeAction, task: () => Promise<unknown>, done: string) => {
    setBusy(action);
    setFailure(null);
    setAnsweredFailure(keptSendFailure ?? null);
    try {
      await task();
    } catch (error) {
      setFailure({ action, error });
      throw error;
    } finally {
      setBusy(null);
    }
    announce(done);
  };

  const setField = <K extends keyof ComposeFields>(key: K, value: ComposeFields[K]) => {
    if (isLocked) return;
    setEdits((current) => ({ ...current, [key]: value }));
    unsavedRef.current = { ...unsavedRef.current, [key]: value };
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => void saveNow(), AUTOSAVE_MS);
    // A warning about text that is no longer there is moot.
    const guard = SEND_GUARDS.find((candidate) => candidate.kind === pending);
    if (guard && !guard.isTriggered(outgoingText({ ...fields, [key]: value }))) setPending(null);
  };

  const startWrite = () => {
    const typed = fields;
    const task = async () => {
      await saveNow();
      aiBodyRef.current = (await writeDraft({ id, fields: typed })).body;
      setEdits((current) => withoutText(current, "subject", "body"));
    };
    run(ComposeAction.Write, task, t("compose.announce.written")).catch(shownOnScreen);
  };

  const write = () => {
    if (isLocked || fields.brief.trim() === "") return;
    // Compared as shown, so turning "Hide details" on or off is not taken for an edit.
    const aiBody = aiBodyRef.current;
    const isAiBody = aiBody !== null && fields.body === shown(aiBody);
    if (fields.body.trim() !== "" && !isAiBody) {
      setPending(ConfirmKind.ReplaceEdits);
      return;
    }
    startWrite();
  };

  const refine = async (instruction: string) => {
    if (isLocked) return;
    const typed = fields;
    const task = async () => {
      await saveNow();
      aiBodyRef.current = (await refineDraft({ id, fields: typed, instruction })).body;
      setEdits((current) => withoutText(current, "body"));
    };
    await run(ComposeAction.Refine, task, t("compose.announce.refined"));
  };

  const dispatchSend = (email: OutgoingEmail) => {
    const task = async () => {
      await saveNow();
      await sendDraft({ id, email });
    };
    run(ComposeAction.Send, task, t("compose.announce.sent")).catch(shownOnScreen);
  };

  const continueSend = (fromGuard: number) => {
    const triggered = SEND_GUARDS.slice(fromGuard).find((guard) =>
      guard.isTriggered(outgoingText(fields)),
    );
    if (triggered) {
      setPending(triggered.kind);
      return;
    }
    const { to, cc, subject, body } = fields;
    void saveNow();
    countdown.start(() => dispatchSend({ to, cc, subject, body, remindIfNoReply }));
  };

  const blockers = sendBlockers(fields, values);

  const send = () => {
    if (isLocked || blockers.length > 0) return;
    setPending(null);
    continueSend(0);
  };

  const confirm = () => {
    const kind = pending;
    setPending(null);
    if (kind === null || isLocked) return;
    if (kind === ConfirmKind.ReplaceEdits) {
      startWrite();
      return;
    }
    continueSend(SEND_GUARDS.findIndex((guard) => guard.kind === kind) + 1);
  };

  const templateGaps = findTemplatePlaceholders(outgoingText(fields)).length;
  const status: DraftWorkflowStatus = {
    failure: null,
    pendingConfirm: pending && {
      kind: pending,
      markerCount: templateGaps,
      text: confirmText(pending, templateGaps, t),
    },
    onConfirm: confirm,
    onCancel: () => setPending(null),
    onSendAtSuggestion: () => undefined,
    isGenerating: false,
    isLoadFailed: false,
    onRetryLoad: () => undefined,
  };

  return {
    fields,
    setField,
    values,
    saveStatus,
    write,
    refine,
    send,
    undoSend: countdown.undo,
    undoCountdown: countdown.secondsLeft,
    remindIfNoReply,
    setRemindIfNoReply,
    settle: (outcome) =>
      void run(
        ComposeAction.Settle,
        () => settleOutcome({ id, outcome }),
        t("compose.announce.settled"),
      ).catch(shownOnScreen),
    remove: () => {
      // No save races the delete; what was typed is dropped only once the draft is gone.
      if (timerRef.current !== null) clearTimeout(timerRef.current);
      timerRef.current = null;
      return run(ComposeAction.Delete, () => deleteDraft(id), t("compose.announce.deleted")).then(
        () => {
          unsavedRef.current = {};
          onDeleted();
        },
      );
    },
    blockers,
    status,
    failure: failure ?? keptFailure(keptSendFailure, answeredFailure, draft.state),
    busy,
    isLocked,
    isSending: busy === ComposeAction.Send || draft.state === ComposeState.Sending,
    announcement,
  };
}
