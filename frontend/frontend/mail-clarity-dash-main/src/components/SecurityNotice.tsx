import { ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useConfirmSender } from "../lib/queries";

/** Shown when an email fails SPF, DKIM or DMARC (#148): no draft until the owner checks the sender.
 *  Mailing lists and forwarding often break DKIM, so a real sender must be confirmable. */
export default function SecurityNotice({ emailId }: { emailId: string }) {
  const { t } = useTranslation();
  const [isConfirming, setIsConfirming] = useState(false);
  const confirm = useConfirmSender();
  return (
    <section
      role="alert"
      className="flex gap-3 rounded-lg border border-danger-line bg-danger-soft p-4"
    >
      <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-danger" />
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-danger">{t("security.spoofTitle")}</h2>
        <p className="text-sm text-fg-body">{t("security.spoofBody")}</p>
        <p className="text-xs text-fg-muted">{t("security.viewInGmail")}</p>
        {isConfirming ? (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-fg-body">{t("security.confirmQuestion")}</span>
            <button
              type="button"
              className="rounded-md border border-danger px-2 py-1 text-xs font-semibold text-danger"
              disabled={confirm.isPending}
              onClick={() => confirm.mutate(emailId)}
            >
              {t("security.confirmYes")}
            </button>
            <button
              type="button"
              className="text-xs text-fg-muted underline"
              onClick={() => setIsConfirming(false)}
            >
              {t("security.confirmNo")}
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="text-xs font-medium text-fg-body underline"
            onClick={() => setIsConfirming(true)}
          >
            {t("security.confirmSender")}
          </button>
        )}
        {confirm.isError ? (
          <p role="alert" className="text-xs text-danger">
            {t("security.confirmFailed")}
          </p>
        ) : null}
      </div>
    </section>
  );
}
