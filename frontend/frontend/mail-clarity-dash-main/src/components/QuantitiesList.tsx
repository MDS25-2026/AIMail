import { Ruler } from "lucide-react";
import { useTranslation } from "react-i18next";

import { UnitSystem } from "../lib/preferences";
import { useFormat } from "../lib/useFormat";
import type { Measure, Quantity } from "../types/email";
import { usePreferences } from "./PreferencesProvider";

/** Conversions for the measurements the sender wrote in the other unit system. Figures already in
 *  the reader's system are left alone: converting them to themselves would only add noise. */
export default function QuantitiesList({ quantities }: { quantities: Quantity[] }) {
  const { t } = useTranslation();
  const format = useFormat();
  const { units } = usePreferences().preferences;
  const foreign = quantities.filter((quantity) => quantity.system !== units);
  if (foreign.length === 0) return null;

  const show = (measure: Measure) => `${format.number(measure.value)} ${measure.unit}`;
  const target = (quantity: Quantity) =>
    units === UnitSystem.Metric ? quantity.metric : quantity.imperial;

  return (
    <div className="mt-3 border-t border-line-subtle pt-3">
      <h3 className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        <Ruler aria-hidden className="size-3" />
        {t("quantities.title")}
      </h3>
      <ul className="mt-1.5 flex flex-wrap gap-1.5">
        {foreign.map((quantity, index) => (
          <li
            key={index}
            className="rounded border border-line bg-surface-muted px-2 py-0.5 text-xs text-fg-body"
          >
            {t("quantities.approx", { written: quantity.text, converted: show(target(quantity)) })}
          </li>
        ))}
      </ul>
    </div>
  );
}
