import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

/** Shown instead of the body and the draft while the listener holds content back (#109). */
export default function QuarantineNotice() {
  const { t } = useTranslation();
  return (
    <section
      role="status"
      className="flex gap-3 rounded-lg border border-warning-line bg-warning-soft p-4"
    >
      <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-warning" />
      <div>
        <h2 className="text-sm font-semibold text-warning">{t("quarantine.title")}</h2>
        <p className="mt-1 text-sm text-fg-body">{t("quarantine.body")}</p>
      </div>
    </section>
  );
}
