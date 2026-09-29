import { CircleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

/**
 * The three states every data-backed page shows before it shows content.
 * Kept in one place so a new page cannot invent its own loading spinner or swallow an error
 * into a blank screen.
 */

export function PageLoading({ label }: { label: string }) {
  const { t } = useTranslation();
  return (
    <p role="status" className="p-6 text-sm text-fg-muted">
      {t("page.loading", { label })}
    </p>
  );
}

export function PageError({ label, error }: { label: string; error: unknown }) {
  const { t } = useTranslation();
  const detail = error instanceof Error ? error.message : t("page.unknownError");
  return (
    <div
      role="alert"
      className="m-6 flex gap-3 rounded-md border border-danger-line bg-danger-soft p-4"
    >
      <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-danger" />
      <div>
        <p className="text-sm font-semibold text-danger">{t("page.errorTitle", { label })}</p>
        <p className="mt-1 text-sm text-danger">{detail}</p>
        <p className="mt-2 text-xs text-danger">{t("page.errorHint")}</p>
      </div>
    </div>
  );
}

export function PageEmpty({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="m-6 rounded-md border border-dashed border-line-strong p-8 text-center">
      <p className="text-sm font-semibold text-fg-body">{title}</p>
      <p className="mt-1 text-sm text-fg-muted">{hint}</p>
    </div>
  );
}
