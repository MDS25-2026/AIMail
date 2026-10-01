import { useTranslation } from "react-i18next";

export default function PiiMaskedBadge({ masked }: { masked: boolean }) {
  const { t } = useTranslation();
  return (
    <span
      title={masked ? t("pii.maskedTitle") : t("pii.noneTitle")}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${
        masked
          ? "bg-brand-soft text-brand ring-1 ring-inset ring-brand-line"
          : "bg-surface-sunken text-fg-muted ring-1 ring-inset ring-line"
      }`}
    >
      {masked ? t("pii.masked") : t("pii.none")}
    </span>
  );
}
