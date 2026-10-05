import { Eye, EyeOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useDetailsHidden } from "../lib/detailsVisibility";

/** Shows placeholders instead of the real details, for screen sharing; remembered per browser. */
export default function DetailsToggle({ isCompact = false }: { isCompact?: boolean }) {
  const { t } = useTranslation();
  const [isHidden, setHidden] = useDetailsHidden();
  const label = isHidden ? t("details.show") : t("details.hide");
  const Icon = isHidden ? Eye : EyeOff;
  return (
    <button
      type="button"
      aria-pressed={isHidden}
      title={label}
      aria-label={isCompact ? label : undefined}
      onClick={() => setHidden(!isHidden)}
      className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-xs font-medium text-fg-muted hover:bg-surface-muted hover:text-fg-body focus-visible:outline-2 focus-visible:outline-brand"
    >
      <Icon aria-hidden className="size-4" />
      {isCompact ? null : label}
    </button>
  );
}
