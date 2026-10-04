import { BookOpen } from "lucide-react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { highlightUsed } from "../lib/highlight";
import type { Source } from "../types/email";

type SourcesChipsProps = {
  sources: Source[];
  /** The draft on screen, so the passage can show which of its sentences the draft uses. */
  draft?: string;
};

export default function SourcesChips({ sources, draft = "" }: SourcesChipsProps) {
  const { t } = useTranslation();
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const panelId = useId();
  if (sources.length === 0) return null;

  const open = openIndex === null ? null : sources[openIndex];

  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("sources.title")}
      </h4>
      <ul className="mt-2 flex flex-wrap gap-1.5">
        {sources.map((source, index) => (
          <li key={source.chunkId ?? index}>
            <button
              type="button"
              aria-expanded={openIndex === index}
              aria-controls={panelId}
              disabled={!source.excerpt}
              onClick={() => setOpenIndex(openIndex === index ? null : index)}
              title={openIndex === index ? t("sources.hide") : t("sources.show")}
              className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${
                openIndex === index
                  ? "border-brand bg-brand-soft text-brand"
                  : "border-line bg-surface-muted text-fg-body hover:bg-surface-sunken"
              }`}
            >
              <BookOpen aria-hidden className="size-3" />
              {source.label}
              {typeof source.score === "number" ? (
                <span className="text-fg-subtle">
                  {t("sources.match", { percent: Math.round(source.score * 100) })}
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>

      {open?.excerpt ? (
        <div id={panelId} className="mt-2 rounded-md border border-line bg-surface-muted p-3">
          <p className="text-sm leading-relaxed text-fg-body">
            {highlightUsed(open.excerpt, draft).map((segment, index) =>
              segment.isUsed ? (
                <mark key={index} className="rounded bg-warning-soft px-0.5 text-fg">
                  {segment.text}{" "}
                </mark>
              ) : (
                <span key={index}>{segment.text} </span>
              ),
            )}
          </p>
          <p className="mt-2 text-[11px] text-fg-subtle">{t("sources.highlightHint")}</p>
        </div>
      ) : null}
    </div>
  );
}
