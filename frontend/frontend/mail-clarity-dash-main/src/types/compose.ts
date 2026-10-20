/** New emails the user writes from a brief (specs/features/compose.md). */
import type { Tone } from "./email";
import { assertSameValues, type Schemas, type WithEnums } from "./schema";

/** Where a new email is; outcome_unknown is locked until the user says whether Gmail sent it. */
export enum ComposeState {
  Draft = "draft",
  Sending = "sending",
  OutcomeUnknown = "outcome_unknown",
  Sent = "sent",
}

/** The user's answer after checking Gmail's Sent folder. */
export enum SettleOutcome {
  Sent = "sent",
  NotSent = "not_sent",
}

/** One saved new email; text in placeholder form, `details` fills it in. */
export type ComposeDraft = WithEnums<
  Schemas["ComposeDraftView"],
  { state: ComposeState; tone: Tone }
>;

export type ComposeSummary = WithEnums<Schemas["ComposeSummary"], { state: ComposeState }>;

export type ComposeList = { drafts: ComposeSummary[]; sent: ComposeSummary[] };

/** Everything the user edits; the API takes any subset of it. */
export type ComposeFields = {
  to: string[];
  cc: string[];
  subject: string;
  brief: string;
  body: string;
  tone: Tone;
};

/** A send that failed, kept past the editor that started it: one fired on leaving reports here. */
export type ComposeSendFailure = { error: unknown };

/** The email exactly as approved; nothing is read back from storage instead. */
export type OutgoingEmail = Omit<Schemas["SendBody"], "cc"> & { cc: string[] };

assertSameValues<`${ComposeState}`, Schemas["ComposeState"]>(true);
assertSameValues<`${SettleOutcome}`, Schemas["SettleOutcome"]>(true);
