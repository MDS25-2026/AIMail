import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { useConfirmSender } from "../lib/queries";
import ConfirmAction from "./ConfirmAction";

/**
 * Shown when an email fails SPF, DKIM or DMARC (#148): no draft until the owner checks the
 * sender. Mailing lists and forwarding often break DKIM, so a real sender must be confirmable.
 */
export default function SecurityNotice({ emailId }: { emailId: string }) {
  const { t } = useTranslation();
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
        <ConfirmAction
          trigger={t("security.confirmSender")}
          question={t("security.confirmQuestion")}
          confirm={t("security.confirmYes")}
          pending={t("security.confirming")}
          cancel={t("security.confirmNo")}
          onConfirm={() => confirm.mutateAsync(emailId)}
          onCancel={confirm.reset}
          isPending={confirm.isPending}
          error={confirm.isError ? errorMessage(confirm.error, t, "security.confirmFailed") : null}
        />
      </div>
    </section>
  );
}
