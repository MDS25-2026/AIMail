import { useTranslation } from "react-i18next";

type ActionItemsListProps = {
  items: string[];
};

export default function ActionItemsList({ items }: ActionItemsListProps) {
  const { t } = useTranslation();
  if (items.length === 0) return null;

  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("actions.title")}
      </h3>
      <ul className="mt-2 space-y-1.5">
        {items.map((item, index) => (
          <li key={index} className="flex gap-2 text-sm text-fg-body">
            <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
