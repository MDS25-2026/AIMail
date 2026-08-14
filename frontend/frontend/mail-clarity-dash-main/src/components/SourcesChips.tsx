import type { Source } from "../types/email";

type SourcesChipsProps = {
  sources: Source[];
};

export default function SourcesChips({ sources }: SourcesChipsProps) {
  if (sources.length === 0) return null;

  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Sources</h4>
      <ul className="mt-2 flex flex-wrap gap-1.5">
        {sources.map((source, index) => (
          <li
            key={index}
            className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600"
          >
            {source.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
