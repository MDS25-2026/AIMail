import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

type ComingSoonProps = {
  title: string;
  description: string;
};

/** Placeholder for a nav destination that is planned but not built. Says so plainly rather
 *  than leaving the tab dead, so the roadmap is visible instead of looking broken. */
export default function ComingSoon({ title, description }: ComingSoonProps) {
  const { t } = useTranslation();
  return (
    <section className="flex min-w-0 flex-1 items-center justify-center bg-surface-muted px-6">
      <div className="max-w-md text-center">
        <span className="inline-block rounded-full bg-brand-soft px-3 py-1 text-xs font-semibold uppercase tracking-wide text-brand">
          {t("comingSoon.badge")}
        </span>
        <h1 className="mt-4 text-2xl font-semibold text-fg">{title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-fg-muted">{description}</p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center rounded-md bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong"
        >
          {t("comingSoon.back")}
        </Link>
      </div>
    </section>
  );
}
