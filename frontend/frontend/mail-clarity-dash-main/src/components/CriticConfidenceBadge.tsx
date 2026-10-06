import { CircleCheck, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { CRITIC_CONFIDENCE_THRESHOLD } from "../types/email";

/** The value drives the styling — 0.8 and above is the project goal. The icon and the words
 *  carry the verdict too, so it never rests on colour alone (WCAG 1.4.1). */
export default function CriticConfidenceBadge({ value }: { value: number }) {
  const { t } = useTranslation();
  const percent = Math.round(value * 100);
  const target = CRITIC_CONFIDENCE_THRESHOLD * 100;
  const isPassing = value >= CRITIC_CONFIDENCE_THRESHOLD;
  const Icon = isPassing ? CircleCheck : TriangleAlert;

  return (
    <span
      title={t(isPassing ? "critic.passingTitle" : "critic.reviewTitle", { percent, target })}
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
        isPassing
          ? "bg-success-soft text-success ring-success-line"
          : "bg-warning-soft text-warning ring-warning-line"
      }`}
    >
      <Icon aria-hidden className="size-3" />
      {t(isPassing ? "critic.passing" : "critic.review", { percent })}
    </span>
  );
}
