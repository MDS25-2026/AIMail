import { assertSameValues, type Schemas, type WithEnums } from "./schema";

/** The signed-in user's audit trail, GET /audit (specs/context/backbone-contracts.md). */

export enum AuditVerification {
  Verified = "verified",
  Tampered = "tampered",
  /** Written before the chain existed, or its hash could not be recomputed: neither OK nor broken. */
  Unverifiable = "unverifiable",
}

/** The parsed `detail` object; rows written before 2026-10-08 arrive as {"text": "<prose>"}. */
export type AuditFields = Readonly<Record<string, string | number | boolean | null>>;

export type AuditTrailEvent = WithEnums<
  Schemas["AuditEventOut"],
  { fields: AuditFields; verification: AuditVerification }
>;

/** headHash: recorded outside the database, it shows if the whole chain was rebuilt. */
export type AuditTrail = WithEnums<Schemas["AuditTrailResponse"], { events: AuditTrailEvent[] }>;

assertSameValues<`${AuditVerification}`, Schemas["Verification"]>(true);
