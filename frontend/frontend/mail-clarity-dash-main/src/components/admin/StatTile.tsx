import type { LucideIcon } from "lucide-react";

type StatTileProps = {
  label: string;
  value: number | string;
  /** A count that means something went wrong: marked with an icon and words, never colour alone. */
  icon?: LucideIcon;
  isAlert?: boolean;
};

export default function StatTile({ label, value, icon: Icon, isAlert = false }: StatTileProps) {
  return (
    <div className="rounded-md border border-line-subtle bg-surface-muted p-3">
      <dt className="flex items-center gap-1 text-xs text-fg-muted">
        {Icon ? (
          <Icon aria-hidden className={`size-3.5 ${isAlert ? "text-danger" : "text-fg-subtle"}`} />
        ) : null}
        {label}
      </dt>
      <dd
        className={`mt-1 text-2xl font-semibold tabular-nums ${isAlert ? "text-danger" : "text-fg"}`}
      >
        {value}
      </dd>
    </div>
  );
}
