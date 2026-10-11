import { CircleCheck, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

type CriticConfidenceBadgeProps = { value: number; isFlagged: boolean };

/** The AI check's verdict in words, with how sure it was. The verdict is the agent's own (any
 *  review reason flags it), so the badge never says "passed" above a list of reasons to check.
 *  The icon and the words carry it too, so it never rests on colour alone (WCAG 1.4.1). */
export default function CriticConfidenceBadge({ value, isFlagged }: CriticConfidenceBadgeProps) {
  const { t } = useTranslation();
  const percent = Math.round(value * 100);
  const Icon = isFlagged ? TriangleAlert : CircleCheck;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${
        isFlagged
          ? "bg-warning-soft text-warning ring-warning-line"
          : "bg-success-soft text-success ring-success-line"
      }`}
    >
      <Icon aria-hidden className="size-3" />
      {t(isFlagged ? "review.flagged" : "review.pass", { percent })}
    </span>
  );
}
