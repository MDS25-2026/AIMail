import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { useSaveScanReading, useScanReading } from "../lib/queries";
import { ScanMode } from "../types/settings";
import { InlineAlert, InlineStatus } from "./InlineMessages";

/** How scanned attachments are read (specs/features/signature-detection.md). */
export default function ScanReadingCard() {
  const { t } = useTranslation();
  const reading = useScanReading();
  const save = useSaveScanReading();
  if (!reading.data) return null;
  const { available, mode } = reading.data;
  const options = [
    { value: ScanMode.Local, label: t("scanReading.local"), hint: t("scanReading.localHint") },
    {
      value: ScanMode.Checked,
      label: t("scanReading.checked"),
      hint: t("scanReading.checkedHint"),
    },
  ];
  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("scanReading.title")}
      </h2>
      <p className="text-sm text-fg-muted">{t("scanReading.intro")}</p>
      <fieldset className="space-y-3">
        <legend className="sr-only">{t("scanReading.title")}</legend>
        {options.map((option) => {
          // Checked stays selectable while it is the saved choice, so the user can see it and leave it.
          const isDisabled =
            save.isPending ||
            (option.value === ScanMode.Checked && !available && mode !== ScanMode.Checked);
          return (
            <label key={option.value} className="flex items-start gap-2">
              <input
                type="radio"
                name="scan-reading"
                value={option.value}
                checked={mode === option.value}
                disabled={isDisabled}
                onChange={() => save.mutate(option.value)}
                className="mt-1 size-4 accent-[var(--brand)]"
              />
              <span>
                <span className="block text-sm font-medium text-fg">{option.label}</span>
                <span className="block text-xs text-fg-subtle">{option.hint}</span>
              </span>
            </label>
          );
        })}
      </fieldset>
      {available ? null : <p className="text-xs text-fg-subtle">{t("scanReading.notSetUp")}</p>}
      <p className="text-xs text-fg-subtle">{t("scanReading.privateNote")}</p>
      {save.isError ? (
        <InlineAlert>{errorMessage(save.error, t, "scanReading.failed")}</InlineAlert>
      ) : null}
      {save.isSuccess ? <InlineStatus>{t("scanReading.saved")}</InlineStatus> : null}
    </section>
  );
}
