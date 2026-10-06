type AISummaryCardProps = {
  summary: string;
};

export default function AISummaryCard({ summary }: AISummaryCardProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-400">AI summary</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-700">{summary}</p>
    </section>
  );
}
