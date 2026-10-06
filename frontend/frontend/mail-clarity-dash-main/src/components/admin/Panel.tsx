import type { ReactNode } from "react";

export default function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-subtle">{title}</h2>
      {children}
    </section>
  );
}
