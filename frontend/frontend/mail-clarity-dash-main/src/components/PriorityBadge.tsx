import { useTranslation } from "react-i18next";

import type { Priority } from "../types/email";

const STYLES: Record<Priority, string> = {
  high: "bg-fg text-surface",
  medium: "border border-line-strong text-fg-body",
  low: "border border-line text-fg-subtle",
};

export default function PriorityBadge({ priority }: { priority: Priority }) {
  const { t } = useTranslation();
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STYLES[priority]}`}
    >
      {t(`priority.${priority}`)}
    </span>
  );
}
