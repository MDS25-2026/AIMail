import { Link } from "@tanstack/react-router";

type ComingSoonProps = {
  title: string;
  description: string;
};

/** Placeholder for a nav destination that is planned but not built. Says so plainly rather
 *  than leaving the tab dead, so the roadmap is visible instead of looking broken. */
export default function ComingSoon({ title, description }: ComingSoonProps) {
  return (
    <section className="flex min-w-0 flex-1 items-center justify-center bg-slate-50 px-6">
      <div className="max-w-md text-center">
        <span className="inline-block rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-blue-600">
          Coming soon
        </span>
        <h1 className="mt-4 text-2xl font-semibold text-slate-800">{title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-500">{description}</p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          Back to inbox
        </Link>
      </div>
    </section>
  );
}
