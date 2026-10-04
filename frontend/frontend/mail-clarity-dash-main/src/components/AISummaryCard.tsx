import { useTranslation } from "react-i18next";

type AISummaryCardProps = {
  summary: string;
};

export default function AISummaryCard({ summary }: AISummaryCardProps) {
  const { t } = useTranslation();
  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("summary.title")}
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-fg-body">{summary}</p>
    </section>
  );
}
