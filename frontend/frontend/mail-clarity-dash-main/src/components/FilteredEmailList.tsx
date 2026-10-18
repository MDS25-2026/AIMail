import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import { detailValues } from "../lib/details";
import { DetailsContext } from "../lib/detailsContext";
import { ListOrder } from "../lib/listOrder";
import { useFormat } from "../lib/useFormat";
import { useEmails } from "../lib/queries";
import type { Email } from "../types/email";
import LoadOlderEmails from "./LoadOlderEmails";
import PriorityBadge from "./PriorityBadge";
import { PageEmpty, PageError, PageLoading } from "./PageState";
import WithDetails from "./WithDetails";

type FilteredEmailListProps = {
  heading: string;
  description: string;
  label: string;
  emptyTitle: string;
  emptyHint: string;
  filter: (email: Email) => boolean;
  /** Which date this view is about — received for drafts, sent for sent. */
  timestampOf: (email: Email) => string;
  order?: ListOrder;
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
  order = ListOrder.NewestFirst,
}: FilteredEmailListProps) {
  const { t } = useTranslation();
  const format = useFormat();
  const emails = useEmails();
  // Newest first by the list's own time: Sent orders by when each reply went out, not when it arrived.
  const rows = (emails.data ?? []).filter(filter).sort((a, b) => {
    const newestFirst = Date.parse(timestampOf(b)) - Date.parse(timestampOf(a));
    return order === ListOrder.NewestFirst ? newestFirst : -newestFirst;
  });

  return (
    <section className="relative min-w-0 flex-1 overflow-y-auto bg-surface-muted p-6">
      <header className="mb-5">
        <h1 className="text-xl font-semibold text-fg">{heading}</h1>
        <p className="mt-1 text-sm text-fg-muted">{description}</p>
      </header>

      {emails.isPending ? <PageLoading label={label} /> : null}
      {emails.isError ? <PageError label={label} error={emails.error} /> : null}
      {emails.data && rows.length === 0 ? <PageEmpty title={emptyTitle} hint={emptyHint} /> : null}

      {rows.length > 0 ? (
        <ul className="relative divide-y divide-line-subtle overflow-hidden rounded-lg border border-line bg-surface">
          {rows.map((email) => (
            // Each row fills in its own email's names, as the inbox rows do (#237).
            <DetailsContext.Provider key={email.id} value={detailValues(email.details)}>
              <li>
                <Link
                  to="/"
                  search={{ email: email.id }}
                  className="block px-4 py-3 transition-colors hover:bg-surface-muted"
                  aria-label={t("sent.open", { subject: email.subject })}
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="truncate text-sm font-semibold text-fg">{email.sender}</span>
                    <span className="shrink-0 text-xs text-fg-subtle">
                      {format.timestamp(timestampOf(email))}
                    </span>
                  </div>
                  <div className="mt-0.5 truncate text-sm text-fg-body">
                    <WithDetails text={email.subject} />
                  </div>
                  <p className="mt-0.5 line-clamp-1 text-xs text-fg-muted">
                    <WithDetails text={email.draftReply || email.preview} />
                  </p>
                  <div className="mt-2">
                    <PriorityBadge priority={email.priority} />
                  </div>
                </Link>
              </li>
            </DetailsContext.Provider>
          ))}
        </ul>
      ) : null}
      <LoadOlderEmails
        hasNextPage={emails.hasNextPage}
        isFetchingNextPage={emails.isFetchingNextPage}
        fetchNextPage={emails.fetchNextPage}
      />
    </section>
  );
}
