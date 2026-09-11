export default function PiiMaskedBadge({ masked }: { masked: boolean }) {
  return (
    <span
      title={masked ? "PII detected and masked in this draft" : "No PII detected in this draft"}
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[11px] font-medium ${
        masked
          ? "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200"
          : "bg-slate-100 text-slate-500 ring-1 ring-inset ring-slate-200"
      }`}
    >
      {masked ? "PII masked" : "No PII"}
    </span>
  );
}
