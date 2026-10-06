import { CRITIC_CONFIDENCE_THRESHOLD } from "../types/email";

/** The value drives the styling — 0.8 and above is the project goal. */
export default function CriticConfidenceBadge({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  const passing = value >= CRITIC_CONFIDENCE_THRESHOLD;

  return (
    <span
      title={
        passing
          ? `Critic Agent confidence ${percent}% (target ${CRITIC_CONFIDENCE_THRESHOLD * 100}%)`
          : `Critic Agent confidence ${percent}% — below the ${
              CRITIC_CONFIDENCE_THRESHOLD * 100
            }% target, review recommended`
      }
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${
        passing
          ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200"
          : "bg-amber-50 text-amber-800 ring-1 ring-inset ring-amber-300"
      }`}
    >
      {passing ? `Critic ${percent}%` : `Critic ${percent}% · review recommended`}
    </span>
  );
}
