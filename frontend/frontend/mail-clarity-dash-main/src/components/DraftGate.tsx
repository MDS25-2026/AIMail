import type { ReactNode } from "react";

import { DraftAvailability } from "../lib/draftAvailability";
import { MaskingStatus, type Email } from "../types/email";
import QuarantineNotice from "./QuarantineNotice";
import SecurityNotice from "./SecurityNotice";
import UnverifiedSenderNotice from "./UnverifiedSenderNotice";

type DraftGateProps = { email: Email; availability: DraftAvailability; children: ReactNode };

/** The one place a panel decides whether the draft shows, so the inbox and the extension agree. */
export default function DraftGate({ email, availability, children }: DraftGateProps) {
  if (availability === DraftAvailability.Quarantined) {
    return <QuarantineNotice isAbandoned={email.masking === MaskingStatus.Abandoned} />;
  }
  if (availability === DraftAvailability.NeedsSenderCheck) {
    return <SecurityNotice emailId={email.id} />;
  }
  if (availability === DraftAvailability.Ready) return children;
  return (
    <>
      <UnverifiedSenderNotice />
      {children}
    </>
  );
}
