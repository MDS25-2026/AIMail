import { TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import { reviewReasonText } from "../lib/reviewReasons";
import type { ReviewReason } from "../types/email";
import WithDetails from "./WithDetails";

/** Why the draft needs the reader, in words on the page rather than in a tooltip. */
export default function ReviewReasonList({ reasons }: { reasons: ReviewReason[] }) {
  const { t } = useTranslation();
  if (reasons.length === 0) return null;
  return (
    <section
      aria-label={t("review.heading")}
      className="mt-2 rounded-md border border-warning-line bg-warning-soft px-3 py-2"
    >
      <h4 className="flex items-center gap-1.5 text-xs font-semibold text-warning">
        <TriangleAlert aria-hidden className="size-3.5" />
        {t("review.heading")}
      </h4>
      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-fg-body">
        {reasons.map((reason, index) => (
          <li key={`${reason.code}-${index}`}>
            {/* Unanswered points are masked email text: the real names come back here. */}
            <WithDetails text={reviewReasonText(reason, t)} />
          </li>
        ))}
      </ul>
    </section>
  );
}
