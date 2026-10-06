import { useTranslation } from "react-i18next";

import { DETAIL_MARK_CLASS, detailSegments } from "../lib/details";
import { useDetailValues } from "../lib/detailsContext";
import { useDetailsHidden } from "../lib/detailsVisibility";

/** Plain text with each placeholder shown as its real detail, marked as hidden from the AI. */
export default function WithDetails({ text }: { text: string }) {
  const { t } = useTranslation();
  const values = useDetailValues();
  const [isHidden] = useDetailsHidden();
  if (isHidden || values.size === 0) return <>{text}</>;
  return (
    <>
      {detailSegments(text, values).map((segment, index) =>
        segment.isDetail ? (
          <mark key={index} className={DETAIL_MARK_CLASS} title={t("details.hiddenFromAi")}>
            {segment.text}
          </mark>
        ) : (
          <span key={index}>{segment.text}</span>
        ),
      )}
    </>
  );
}
