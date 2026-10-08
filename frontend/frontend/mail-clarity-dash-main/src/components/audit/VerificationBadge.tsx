import { CircleHelp, ShieldAlert, ShieldCheck, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { AuditVerification } from "../../types/audit";

type Look = { icon: LucideIcon; className: string };

// Unverifiable is drawn neutral, never green: a record nobody could check has not passed.
const LOOK: Record<AuditVerification, Look> = {
  [AuditVerification.Verified]: {
    icon: ShieldCheck,
    className: "border-success-line bg-success-soft text-success",
  },
  [AuditVerification.Tampered]: {
    icon: ShieldAlert,
    className: "border-danger-line bg-danger-soft text-danger",
  },
  [AuditVerification.Unverifiable]: {
    icon: CircleHelp,
    className: "border-line-strong bg-surface-sunken text-fg-muted",
  },
};

export default function VerificationBadge({ verification }: { verification: AuditVerification }) {
  const { t } = useTranslation();
  const { icon: Icon, className } = LOOK[verification];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-semibold ${className}`}
    >
      <Icon aria-hidden className="size-3.5" />
      {t(`audit.verification.${verification}`)}
    </span>
  );
}
