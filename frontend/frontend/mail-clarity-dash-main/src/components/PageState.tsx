/**
 * The three states every data-backed page shows before it shows content.
 * Kept in one place so a new page cannot invent its own loading spinner or swallow an error
 * into a blank screen.
 */

export function PageLoading({ label }: { label: string }) {
  return (
    <p role="status" className="p-6 text-sm text-slate-500">
      Loading {label}…
    </p>
  );
}

export function PageError({ label, error }: { label: string; error: unknown }) {
  const detail = error instanceof Error ? error.message : "Unknown error";
  return (
    <div role="alert" className="m-6 rounded-md border border-red-200 bg-red-50 p-4">
      <p className="text-sm font-semibold text-red-800">Could not load {label}</p>
      <p className="mt-1 text-sm text-red-700">{detail}</p>
      <p className="mt-2 text-xs text-red-600">
        Check the backend is running on the configured URL and that the API token matches.
      </p>
    </div>
  );
}

export function PageEmpty({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="m-6 rounded-md border border-dashed border-slate-300 p-8 text-center">
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      <p className="mt-1 text-sm text-slate-500">{hint}</p>
    </div>
  );
}
