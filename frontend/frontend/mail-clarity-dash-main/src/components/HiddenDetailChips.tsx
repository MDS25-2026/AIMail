import { EyeOff } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { DetailValues } from "../lib/details";
import { fillFirst, unfilledMarkers } from "../lib/hiddenDetails";
import { kindOf } from "../lib/masking";
import { cn } from "../lib/utils";
import { button, field } from "./variants";

type HiddenDetailChipsProps = {
  draft: string;
  values: DetailValues;
  onDraftChange: (draft: string) => void;
  disabled?: boolean;
};

/** A chip per detail the AI never saw and AIMail cannot fill back in (#158); tap to type it in. */
export default function HiddenDetailChips({
  draft,
  values,
  onDraftChange,
  disabled = false,
}: HiddenDetailChipsProps) {
  const { t } = useTranslation();
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [typed, setTyped] = useState("");
  const markers = unfilledMarkers(draft, values);
  if (markers.length === 0) return null;
  const open = openIndex === null ? null : markers[openIndex];

  const toggle = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
    setTyped("");
  };

  const fill = () => {
    if (!open) return;
    onDraftChange(fillFirst(draft, open, typed));
    setOpenIndex(null);
    setTyped("");
  };

  return (
    <div className="space-y-2">
      <p className="text-xs text-fg-muted">{t("hiddenDetails.intro", { count: markers.length })}</p>
      <ul className="flex flex-wrap gap-1.5">
        {markers.map((marker, index) => (
          <li key={`${marker}-${index}`}>
            <button
              type="button"
              disabled={disabled}
              aria-expanded={openIndex === index}
              onClick={() => toggle(index)}
              className="inline-flex items-center gap-1 rounded-full border border-brand-line bg-brand-soft px-2 py-0.5 text-xs text-brand"
            >
              <EyeOff aria-hidden className="size-3" />
              {t(`hiddenDetails.kind.${kindOf(marker)}`)}
            </button>
          </li>
        ))}
      </ul>
      {open ? (
        <div className="space-y-2 rounded-md border border-line bg-surface-muted p-3 text-sm">
          <p className="text-fg-body">{t("hiddenDetails.explain")}</p>
          <div className="flex flex-wrap gap-2">
            <input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && fill()}
              aria-label={t("hiddenDetails.typeHere")}
              placeholder={t("hiddenDetails.typeHere")}
              className={cn(field({ size: "sm" }), "min-w-0 flex-1")}
            />
            <button
              type="button"
              disabled={!typed.trim()}
              onClick={fill}
              className={button({ intent: "primary", size: "xs" })}
            >
              {t("hiddenDetails.fill")}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
