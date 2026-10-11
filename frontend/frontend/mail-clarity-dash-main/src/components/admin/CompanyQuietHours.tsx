import { useTranslation } from "react-i18next";

import { errorMessage } from "../../lib/api/errors";
import { useCompanyQuietHours, useSaveCompanyQuietHours } from "../../lib/queries";
import { InlineAlert, InlineStatus } from "../InlineMessages";
import { PageError, PageLoading } from "../PageState";
import QuietHoursForm from "../QuietHoursForm";

/** The company's default quiet hours; each person can still set their own in Settings. */
export default function CompanyQuietHours() {
  const { t } = useTranslation();
  const hours = useCompanyQuietHours(true);
  const save = useSaveCompanyQuietHours();
  return (
    <div className="space-y-3">
      <p className="text-sm text-fg-muted">{t("admin.quietHoursHint")}</p>
      {hours.isPending ? <PageLoading label={t("quietHours.title")} /> : null}
      {hours.isError ? <PageError label={t("quietHours.title")} error={hours.error} /> : null}
      {hours.data ? (
        <QuietHoursForm
          key={JSON.stringify(hours.data)}
          initial={hours.data}
          isSaving={save.isPending}
          onSave={(next) => save.mutate(next)}
        />
      ) : null}
      {save.isError ? (
        <InlineAlert>{errorMessage(save.error, t, "quietHours.failed")}</InlineAlert>
      ) : null}
      {save.isSuccess ? <InlineStatus>{t("quietHours.saved")}</InlineStatus> : null}
    </div>
  );
}
