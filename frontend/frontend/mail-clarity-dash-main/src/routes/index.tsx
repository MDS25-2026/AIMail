import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import InboxList from "../components/InboxList";
import LoadOlderEmails from "../components/LoadOlderEmails";
import EmailDetailPanel from "../components/EmailDetailPanel";
import AppShell from "../components/AppShell";
import { PageEmpty, PageError, PageLoading } from "../components/PageState";
import { Page, pageMeta } from "../lib/pageMeta";
import { useEmail, useEmails, useSession } from "../lib/queries";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import { useDraftWorkflow } from "../lib/useDraftWorkflow";

type InboxSearch = { email?: string };

export const Route = createFileRoute("/")({
  // ?email=<id> opens that email, so Sent and other lists can link straight to one.
  validateSearch: (search: Record<string, unknown>): InboxSearch => ({
    email: typeof search.email === "string" ? search.email : undefined,
  }),
  head: ({ match }) => ({
    meta: [
      ...pageMeta(match.context.preferences.language, Page.Inbox),
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DashboardPage,
});

// Long enough to skip rows passed with J/K, short enough not to be felt on a click.
const SELECTION_SETTLE_MS = 150;

function DashboardPage() {
  const { t } = useTranslation();
  const { email: requestedId } = Route.useSearch();
  const emails = useEmails();
  const session = useSession();
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  // Opened once the selection settles, so stepping through with J/K doesn't fetch (and mark read) every row.
  const openedEmailId = useDebouncedValue(selectedEmailId, SELECTION_SETTLE_MS);
  const selected = useEmail(openedEmailId);

  // Show the list row's copy until the detail lands; never a previous email's detail while settling.
  const listEmail = (emails.data ?? []).find((item) => item.id === selectedEmailId) ?? null;
  const detail = selected.data?.id === selectedEmailId ? selected.data : undefined;
  const email = detail ?? listEmail;
  const workflow = useDraftWorkflow(email, selected);

  const didAutoSelectRef = useRef(false);
  useEffect(() => {
    // Auto-select once: the email the link asked for, else the first. StrictMode double-invokes
    // effects in dev, hence the ref.
    const requested = emails.data?.find((item) => item.id === requestedId);
    const first = requested ?? emails.data?.[0];
    if (first && !didAutoSelectRef.current) {
      didAutoSelectRef.current = true;
      setSelectedEmailId(first.id);
    }
  }, [emails.data]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <AppShell>
      <>
        {/* Read out when a slow action finishes, since the result appears elsewhere. */}
        <p role="status" aria-live="polite" className="sr-only">
          {workflow.announcement}
        </p>
        <aside className="min-h-0 w-80 shrink-0 border-r border-line bg-surface">
          {emails.isPending ? <PageLoading label={t("inbox.heading")} /> : null}
          {emails.isError ? (
            <PageError
              label={t("inbox.heading")}
              error={emails.error}
              onRetry={() => void emails.refetch()}
            />
          ) : null}
          {emails.data?.length === 0 && session.data?.hasMailbox === false ? (
            <PageEmpty title={t("inbox.noMailboxTitle")} hint={t("inbox.noMailboxHint")} />
          ) : null}
          {emails.data?.length === 0 && session.data?.hasMailbox !== false ? (
            <PageEmpty title={t("inbox.emptyTitle")} hint={t("inbox.emptyHint")} />
          ) : null}
          {emails.data && emails.data.length > 0 ? (
            <InboxList
              emails={emails.data}
              selectedEmailId={selectedEmailId}
              onSelectEmail={setSelectedEmailId}
            />
          ) : null}
          <LoadOlderEmails
            hasNextPage={emails.hasNextPage}
            isFetchingNextPage={emails.isFetchingNextPage}
            fetchNextPage={emails.fetchNextPage}
          />
        </aside>

        <section className="min-h-0 min-w-0 flex-1 bg-surface-muted">
          <EmailDetailPanel email={email} workflow={workflow} />
        </section>
      </>
    </AppShell>
  );
}
