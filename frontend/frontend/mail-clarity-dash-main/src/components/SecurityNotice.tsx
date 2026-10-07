import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

/** Shown when an email fails SPF, DKIM or DMARC domain verification (#148).
 *  Automated draft generation is suppressed to protect against phishing and domain spoofing. */
export default function SecurityNotice() {
  const { t } = useTranslation();
  return (
    <section
      role="alert"
      className="flex gap-3 rounded-lg border border-danger-line bg-danger-soft p-4"
    >
      <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-danger" />
      <div>
        <h2 className="text-sm font-semibold text-danger">{t("security.spoofTitle")}</h2>
        <p className="mt-1 text-sm text-fg-body">{t("security.spoofBody")}</p>
        <p className="mt-2 text-xs text-fg-muted">{t("security.viewInGmail")}</p>
      </div>
    </section>
  );
}
