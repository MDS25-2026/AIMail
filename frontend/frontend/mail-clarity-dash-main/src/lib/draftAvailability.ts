import { AuthStatus, MaskingStatus, type Email } from "../types/email";

/** What an email may do, by the backend's refusal_for rules (specs/context/backbone-contracts.md). */
export enum DraftAvailability {
  /** Masking is pending or abandoned: nothing to read or draft from. */
  Quarantined = "quarantined",
  /** SPF, DKIM or DMARC failed: no draft until the owner confirms the sender. */
  NeedsSenderCheck = "needsSenderCheck",
  Ready = "ready",
  /** No verdict on the sender: drafting is allowed, with a notice. */
  ReadyUnverified = "readyUnverified",
}

type AvailabilityInput = Pick<Email, "authStatus" | "masking">;

const WITHHELD: ReadonlySet<MaskingStatus | undefined> = new Set([
  MaskingStatus.Pending,
  MaskingStatus.Abandoned,
]);
// Unknown always reads as unverified, never as pass.
const VERIFIED: ReadonlySet<AuthStatus | undefined> = new Set([
  AuthStatus.Pass,
  AuthStatus.SenderConfirmed,
]);

export function isQuarantined(email: AvailabilityInput): boolean {
  return WITHHELD.has(email.masking);
}

export function draftAvailability(email: AvailabilityInput): DraftAvailability {
  if (isQuarantined(email)) return DraftAvailability.Quarantined;
  if (email.authStatus === AuthStatus.SpoofDetected) return DraftAvailability.NeedsSenderCheck;
  if (VERIFIED.has(email.authStatus)) return DraftAvailability.Ready;
  return DraftAvailability.ReadyUnverified;
}
