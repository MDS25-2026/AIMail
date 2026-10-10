import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { useFollowCompanyQuietHours, useQuietHours, useSaveQuietHours } from "../lib/queries";
import { InlineAlert, InlineStatus } from "./InlineMessages";
import QuietHoursForm from "./QuietHoursForm";

/** Settings > Quiet hours (specs/features/quiet-hours-send-later.md): advice on when to send. */
export default function QuietHoursCard() {
  const { t } = useTranslation();
  const settings = useQuietHours();
  const save = useSaveQuietHours();
  const follow = useFollowCompanyQuietHours();
  if (!settings.data) return null;
  const { company, personal, effective } = settings.data;
  const failure = save.error ?? follow.error;

  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("quietHours.title")}
      </h2>
      <p className="text-sm text-fg-muted">{t("quietHours.intro")}</p>
      <label className="flex min-h-11 items-center gap-2 text-sm font-medium text-fg md:min-h-0">
        <input
          type="checkbox"
          checked={personal !== null}
          disabled={save.isPending || follow.isPending}
          onChange={(event) => (event.target.checked ? save.mutate(company) : follow.mutate())}
          className="size-4 accent-[var(--brand)]"
        />
        {t("quietHours.useMine")}
      </label>
      {personal ? (
        <QuietHoursForm
          key={JSON.stringify(personal)}
          initial={personal}
          isSaving={save.isPending}
          onSave={(hours) => save.mutate(hours)}
        />
      ) : (
        <p className="text-xs text-fg-subtle">
          {t("quietHours.following", {
            from: effective.start.slice(0, 5),
            to: effective.end.slice(0, 5),
          })}
        </p>
      )}
      {failure ? <InlineAlert>{errorMessage(failure, t, "quietHours.failed")}</InlineAlert> : null}
      {save.isSuccess || follow.isSuccess ? (
        <InlineStatus>{t("quietHours.saved")}</InlineStatus>
      ) : null}
    </section>
  );
}
