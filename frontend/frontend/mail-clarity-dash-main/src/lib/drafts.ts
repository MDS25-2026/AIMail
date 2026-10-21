import { AuthStatus, type Email } from "../types/email";
import { isQuarantined } from "./draftAvailability";

/**
 * A draft waiting for the reader (specs/features/drafts-page.md): written, not sent, not already
 * approved for later, not answered some other way (a reply from Gmail sets isAnswered), and one
 * the inbox would show for review. A spoofed sender's draft sits behind SecurityNotice and a
 * quarantined email has none to show, so neither is listed.
 */
export function isPendingDraft(email: Email): boolean {
  return (
    email.draftReply.trim() !== "" &&
    !email.sentAt &&
    !email.isAnswered &&
    !email.scheduledFor &&
    !email.isDrafting &&
    email.authStatus !== AuthStatus.SpoofDetected &&
    !isQuarantined(email)
  );
}
