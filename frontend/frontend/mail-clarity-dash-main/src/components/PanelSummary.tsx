import { useState } from "react";
import { useTranslation } from "react-i18next";

import WithDetails from "./WithDetails";

/** The summary and action items folded into three lines, so the reply sits near the top. */
export default function PanelSummary({
  summary,
  actionItems,
}: {
  summary: string;
  actionItems: string[];
}) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  if (!summary && actionItems.length === 0) return null;
  return (
    <section
      aria-label={t("extension.summary")}
      className="rounded-lg border border-line bg-surface p-3"
    >
      <p className={`text-sm text-fg-body ${isOpen ? "" : "line-clamp-3"}`}>
        <WithDetails text={summary} />
      </p>
      {isOpen && actionItems.length > 0 ? (
        <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-fg-muted">
          {actionItems.map((item) => (
            <li key={item}>
              <WithDetails text={item} />
            </li>
          ))}
        </ul>
      ) : null}
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((value) => !value)}
        className="mt-2 text-xs font-medium text-brand hover:text-brand-strong"
      >
        {isOpen ? t("extension.showLess") : t("extension.showMore", { count: actionItems.length })}
      </button>
    </section>
  );
}
