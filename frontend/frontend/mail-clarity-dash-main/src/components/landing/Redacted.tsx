import { useTranslation } from "react-i18next";

import { SAMPLE } from "./sample";

type Detail = keyof typeof SAMPLE;

const TOKEN = /\[(name|email|phone)\]/;

function isDetail(part: string): part is Detail {
  return part in SAMPLE;
}

/** A template's [name], [email] and [phone] as the real value, or as the placeholder the AI sees. */
export function Filled({ template, isHidden }: { template: string; isHidden: boolean }) {
  const { t } = useTranslation();
  return (
    <>
      {template.split(TOKEN).map((part, index) => {
        if (index % 2 === 0 || !isDetail(part)) return part;
        return isHidden ? (
          <span
            key={index}
            className="mx-0.5 inline-flex items-center rounded border border-brand/40 bg-brand-soft px-1 font-mono text-[0.85em] text-brand"
          >
            {t(`landing.preview.placeholders.${part}`)}
          </span>
        ) : (
          <span key={index} className="font-medium text-fg">
            {SAMPLE[part]}
          </span>
        );
      })}
    </>
  );
}
