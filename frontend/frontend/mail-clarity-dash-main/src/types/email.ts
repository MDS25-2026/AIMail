/**
 * Single source of truth for the email shape.
 * The ingestion / retrieval / generation lanes will eventually fill these in
 * for real — treat field names as fixed unless the team changes them together.
 */

export type Priority = "high" | "medium" | "low";
export type Tone = "professional" | "casual";

import { assertSameValues, type Schemas, type WithEnums } from "./schema";

export type ThreadMessage = Schemas["ThreadMessage"];
export type Source = Schemas["Source"];
export type Measure = Schemas["MeasureView"];
export type Quantity = Schemas["QuantityView"];
export type Detail = Schemas["Detail"];
export type EgressRecord = Schemas["EgressRecord"];
export type Translation = { language: string; text: string };

/** The detail and list views of an email, with the finite sets as this app's enums. */
export type Email = WithEnums<
  Schemas["DashboardEmail"],
  { authStatus?: AuthStatus; masking?: MaskingStatus; priority: Priority; tone: Tone }
>;

/** One page of the inbox; nextCursor fetches the next, and is null on the last page. */
export type EmailPage = WithEnums<Schemas["EmailPage"], { emails: Email[] }>;

export enum AuthStatus {
  Pass = "pass",
  SpoofDetected = "spoof_detected",
  Unverified = "unverified",
  SenderConfirmed = "sender_confirmed",
}

/** Pending: content withheld until it can be fully masked; abandoned: it never will be (#109). */
export enum MaskingStatus {
  Complete = "complete",
  Pending = "pending",
  Abandoned = "abandoned",
}

/** Below this the draft is flagged "review recommended". */
export const CRITIC_CONFIDENCE_THRESHOLD = 0.8;

assertSameValues<`${AuthStatus}`, Schemas["AuthStatus"]>(true);
assertSameValues<`${MaskingStatus}`, Schemas["DashboardEmail"]["masking"]>(true);
assertSameValues<Tone, Schemas["Tone"]>(true);
