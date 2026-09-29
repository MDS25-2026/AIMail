import { useTranslation } from "react-i18next";

import type { Count } from "../../types/admin";

/**
 * A ranked horizontal bar list: one series, one hue, the value printed beside every bar in text
 * colour, so the list is its own table view and nothing depends on reading the bar length.
 */
export default function BarList({ items, label }: { items: Count[]; label: string }) {
  const { t } = useTranslation();
  if (items.length === 0) return <p className="text-sm text-fg-subtle">{t("admin.noData")}</p>;
  const largest = Math.max(...items.map((item) => item.count));

  return (
    <ul aria-label={label} className="space-y-2">
      {items.map((item) => (
        <li key={item.label} title={`${item.label}: ${item.count}`} className="text-sm">
          <div className="flex items-baseline justify-between gap-3">
            <span className="truncate text-fg-body">{item.label}</span>
            <span className="shrink-0 font-medium tabular-nums text-fg">{item.count}</span>
          </div>
          <div className="mt-1 h-2 rounded-full bg-surface-sunken" aria-hidden>
            <div
              className="h-2 rounded-full bg-brand"
              style={{ width: `${Math.max(2, (item.count / largest) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
