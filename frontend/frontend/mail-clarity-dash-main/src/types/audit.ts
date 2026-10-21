import { assertSameValues, type Schemas, type WithEnums } from "./schema";

/** The company audit trail, GET /audit, for admins (specs/features/admin-only-pages.md). */

export enum AuditVerification {
  Verified = "verified",
  Tampered = "tampered",
  /** Written before the chain existed, or its hash could not be recomputed: neither OK nor broken. */
  Unverifiable = "unverifiable",
}

/** backend/app/audit_groups.py; Other holds any action not listed, so nothing is hidden. */
export enum ActionGroup {
  Sending = "sending",
  Drafting = "drafting",
  Privacy = "privacy",
  Mailbox = "mailbox",
  Settings = "settings",
  Admin = "admin",
  Other = "other",
}

export enum AuditWindow {
  Day = "day",
  Week = "week",
  Month = "month",
  All = "all",
}

/** The parsed `detail` object; rows written before 2026-10-08 arrive as {"text": "<prose>"}. */
export type AuditFields = Readonly<Record<string, string | number | boolean | null>>;

export type AuditTrailEvent = WithEnums<
  Schemas["AuditEventOut"],
  { fields: AuditFields; verification: AuditVerification; group: ActionGroup }
>;

export type AuditPerson = Schemas["AuditPerson"];

/** headHash: recorded outside the database, it shows if the whole chain was rebuilt. */
export type AuditTrail = WithEnums<Schemas["AuditTrailResponse"], { events: AuditTrailEvent[] }>;

/** What the admin narrows the trail to; null means "any". */
export type AuditFilters = {
  group: ActionGroup | null;
  person: string | null;
  isFailuresOnly: boolean;
  window: AuditWindow;
};

export const NO_AUDIT_FILTERS: AuditFilters = {
  group: null,
  person: null,
  isFailuresOnly: false,
  window: AuditWindow.All,
};

assertSameValues<`${AuditVerification}`, Schemas["Verification"]>(true);
assertSameValues<`${ActionGroup}`, Schemas["ActionGroup"]>(true);
assertSameValues<`${AuditWindow}`, Schemas["AuditWindow"]>(true);
