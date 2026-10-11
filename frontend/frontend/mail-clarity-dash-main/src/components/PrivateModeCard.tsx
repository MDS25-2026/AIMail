import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { usePrivateMode, useSavePrivateMode } from "../lib/queries";
import { InlineAlert, InlineStatus } from "./InlineMessages";

/** Private mode (specs/features/local-model.md). Hidden unless the company has set up a local model. */

export default function PrivateModeCard() {
  const { t } = useTranslation();
  const mode = usePrivateMode();
  const save = useSavePrivateMode();
  // Still shown when it is on but no longer offered, so the user can always switch it off.
  if (!mode.data || !(mode.data.available || mode.data.enabled)) return null;
  const isStranded = mode.data.enabled && !mode.data.available;
  const notes = [mode.data.search ? "search" : "noSearch", "n2"] as const;
  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("privateMode.title")}
      </h2>
      <label className="flex min-h-11 items-center gap-2 text-sm font-medium text-fg md:min-h-0">
        <input
          type="checkbox"
          checked={mode.data.enabled}
          disabled={save.isPending}
          onChange={(event) => save.mutate(event.target.checked)}
          className="size-4 accent-[var(--brand)]"
        />
        {t("privateMode.switch")}
      </label>
      {isStranded ? (
        <InlineAlert>{t("privateMode.notSetUp")}</InlineAlert>
      ) : (
        <p className="text-sm text-fg-muted">
          {t("privateMode.intro", { model: mode.data.model })}
        </p>
      )}
      <ul className="list-disc space-y-1 pl-5 text-xs text-fg-subtle">
        {notes.map((note) => (
          <li key={note}>{t(`privateMode.notes.${note}`)}</li>
        ))}
      </ul>
      {save.isError ? (
        <InlineAlert>{errorMessage(save.error, t, "privateMode.failed")}</InlineAlert>
      ) : null}
      {save.isSuccess ? (
        <InlineStatus>
          {mode.data.enabled ? t("privateMode.on") : t("privateMode.off")}
        </InlineStatus>
      ) : null}
    </section>
  );
}
