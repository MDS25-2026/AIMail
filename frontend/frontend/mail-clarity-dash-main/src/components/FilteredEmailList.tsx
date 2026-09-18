import { Link } from "@tanstack/react-router";

import { formatTimestamp } from "../lib/formatTimestamp";
import { useEmails } from "../lib/queries";
import type { Email } from "../types/email";
import PriorityBadge from "./PriorityBadge";
import { PageEmpty, PageError, PageLoading } from "./PageState";

type FilteredEmailListProps = {
  heading: string;
  description: string;
  label: string;
  emptyTitle: string;
  emptyHint: string;
  filter: (email: Email) => boolean;
  /** Which date this view is about — received for drafts, sent for sent. */
  timestampOf: (email: Email) => string;
};

/**
 * Drafts and Sent are the same list over the same /emails payload, differing only in which
 * rows they keep and which date they show. Filtering on the client is deliberate at this size:
 * the dashboard already holds every email in cache, so a status query parameter would add an
 * API contract for no gain. Revisit if the mailbox ever outgrows one page of results.
 */
export default function FilteredEmailList({
  heading,
  description,
  label,
  emptyTitle,
  emptyHint,
  filter,
  timestampOf,
}: FilteredEmailListProps) {
  const emails = useEmails();
  const rows = (emails.data ?? []).filter(filter);

  return (
    <section className="min-w-0 flex-1 overflow-y-auto bg-slate-50 p-6">
      <header className="mb-5">
        <h1 className="text-xl font-semibold text-slate-800">{heading}</h1>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </header>

      {emails.isPending ? <PageLoading label={label} /> : null}
      {emails.isError ? <PageError label={label} error={emails.error} /> : null}
      {emails.data && rows.length === 0 ? (
        <PageEmpty title={emptyTitle} hint={emptyHint} />
      ) : null}

      {rows.length > 0 ? (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-lg border border-slate-200 bg-white">
          {rows.map((email) => (
            <li key={email.id}>
              <Link
                to="/"
                className="block px-4 py-3 transition-colors hover:bg-slate-50"
                aria-label={`Open ${email.subject} in the inbox`}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-sm font-semibold text-slate-800">
                    {email.sender}
                  </span>
                  <span className="shrink-0 text-xs text-slate-400">
                    {formatTimestamp(timestampOf(email))}
                  </span>
                </div>
                <div className="mt-0.5 truncate text-sm text-slate-700">{email.subject}</div>
                <p className="mt-0.5 line-clamp-1 text-xs text-slate-500">
                  {email.draftReply || email.preview}
                </p>
                <div className="mt-2">
                  <PriorityBadge priority={email.priority} />
                </div>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
