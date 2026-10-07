import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { fetchPrivateMode, savePrivateMode } from "../lib/api";

/** Private mode (specs/features/local-model.md). Hidden unless the company has set up a local model. */

const PRIVATE_MODE_KEY = ["private-mode"] as const;

export default function PrivateModeCard() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const mode = useQuery({ queryKey: PRIVATE_MODE_KEY, queryFn: fetchPrivateMode });
  const save = useMutation({
    mutationFn: savePrivateMode,
    onSuccess: (saved) => queryClient.setQueryData(PRIVATE_MODE_KEY, saved),
  });
  // Still shown when it is on but no longer offered, so the user can always switch it off.
  if (!mode.data || !(mode.data.available || mode.data.enabled)) return null;
  const isStranded = mode.data.enabled && !mode.data.available;
  const notes = [mode.data.search ? "search" : "noSearch", "n2", "n3"] as const;
  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("privateMode.title")}
      </h2>
      <label className="flex items-center gap-2 text-sm font-medium text-fg">
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
        <p role="alert" className="text-sm text-danger">
          {t("privateMode.notSetUp")}
        </p>
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
        <p role="alert" className="text-sm text-danger">
          {t("privateMode.failed")}
        </p>
      ) : null}
      {save.isSuccess ? (
        <p role="status" className="text-sm text-success">
          {mode.data.enabled ? t("privateMode.on") : t("privateMode.off")}
        </p>
      ) : null}
    </section>
  );
}
