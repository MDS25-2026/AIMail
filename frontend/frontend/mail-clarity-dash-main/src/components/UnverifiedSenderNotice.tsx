import { ShieldQuestion } from "lucide-react";
import { useTranslation } from "react-i18next";

/** No verdict on the sender (auth_status unverified): drafting goes ahead, but the reader is told. */
export default function UnverifiedSenderNotice() {
  const { t } = useTranslation();
  return (
    <p
      role="status"
      className="flex gap-2 rounded-md border border-warning-line bg-warning-soft px-3 py-2 text-xs text-fg-body"
    >
      <ShieldQuestion aria-hidden className="mt-0.5 size-4 shrink-0 text-warning" />
      {t("security.unverified")}
    </p>
  );
}
