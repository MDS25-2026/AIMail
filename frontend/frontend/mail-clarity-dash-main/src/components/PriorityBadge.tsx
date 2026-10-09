import { OctagonAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { Priority } from "../types/email";

const STYLES: Record<Priority, string> = {
  // The most urgent tier is the boldest badge. Solid red beside "high"'s solid near-black can read
  // as two dark badges to red-blind readers, so critical also carries an icon (WCAG 1.4.1).
  critical: "gap-1 bg-danger text-surface",
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
      {priority === "critical" ? <OctagonAlert aria-hidden className="size-3" /> : null}
      {t(`priority.${priority}`)}
    </span>
  );
}
