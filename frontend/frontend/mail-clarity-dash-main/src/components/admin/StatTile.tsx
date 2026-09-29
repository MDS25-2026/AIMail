import type { LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

type StatTileProps = {
  label: string;
  value: number | string;
  /** Shown only when the value needs attention, with words for screen readers: never colour alone. */
  icon?: LucideIcon;
  isAlert?: boolean;
};

export default function StatTile({ label, value, icon: Icon, isAlert = false }: StatTileProps) {
  const { t } = useTranslation();
  return (
    <div
      className={`rounded-md border p-3 ${
        isAlert ? "border-danger-line bg-danger-soft" : "border-line-subtle bg-surface-muted"
      }`}
    >
      <dt className="flex items-center gap-1 text-xs text-fg-muted">
        {isAlert && Icon ? <Icon aria-hidden className="size-3.5 text-danger" /> : null}
        {label}
        {isAlert ? <span className="sr-only">{t("admin.needsAttention")}</span> : null}
      </dt>
      <dd
        className={`mt-1 text-2xl font-semibold tabular-nums ${isAlert ? "text-danger" : "text-fg"}`}
      >
        {value}
      </dd>
    </div>
  );
}
