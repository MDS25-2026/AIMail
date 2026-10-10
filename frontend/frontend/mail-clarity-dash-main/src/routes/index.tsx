import { createFileRoute, useCanGoBack, useNavigate, useRouter } from "@tanstack/react-router";
import { useState } from "react";
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

// Tailwind's md breakpoint: below it the inbox shows the list or one email, not both.
const PHONE_QUERY = "(max-width: 767px)";

function isPhone(): boolean {
  return typeof window !== "undefined" && window.matchMedia(PHONE_QUERY).matches;
}

// Long enough to skip rows passed with J/K, short enough not to be felt on a click.
const SELECTION_SETTLE_MS = 150;

function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { email: requestedId } = Route.useSearch();
  const emails = useEmails();
  const session = useSession();
  const [userSelectedId, setUserSelectedId] = useState<string | null>(null);

  // Derive selected email from URL search params, explicit selection, or first inbox email
  const selectedEmailId =
    requestedId ??
    userSelectedId ??
    (emails.data && emails.data.length > 0 ? emails.data[0].id : null);
  // Opened once the selection settles, so stepping through with J/K doesn't fetch (and mark read) every row.
  const openedEmailId = useDebouncedValue(selectedEmailId, SELECTION_SETTLE_MS);
  const selected = useEmail(openedEmailId);
  // Never a previous email's detail while the selection settles.
  const detail = selected.data?.id === selectedEmailId ? selected.data : undefined;

  // Back when the app opened this email; to the inbox when it was opened from a link.
  const router = useRouter();
  const canGoBack = useCanGoBack();
  const backToInbox = () =>
    canGoBack ? router.history.back() : void navigate({ to: "/", search: {} });

  const handleSelectEmail = (id: string) => {
    setUserSelectedId(id);
    void navigate({
      to: "/",
      search: { email: id },
      // On a phone opening an email is a step the back button undoes; on a desktop J/K would
      // otherwise fill the history with every row passed.
      replace: !isPhone(),
    });
  };

  // If an email was opened directly via search/deep-link and is not in the loaded inbox page,
  // include it in the display list so it is highlighted in the list
  const displayEmails =
    detail && !emails.data?.some((item) => item.id === detail.id)
      ? [detail, ...(emails.data ?? [])]
      : (emails.data ?? []);

  // The detail call re-runs generation (~15s), so show the list row's copy until it lands.
  const listEmail = displayEmails.find((item) => item.id === selectedEmailId) ?? null;
  const email = detail ?? listEmail;
  const workflow = useDraftWorkflow(email, selected);

  return (
    <AppShell>
      <>
        {/* Read out when a slow action finishes, since the result appears elsewhere. */}
        <p role="status" aria-live="polite" className="sr-only">
          {workflow.announcement}
        </p>
        {/* A phone shows the list until an email is opened (?email=), then only the email. */}
        <aside
          className={`min-h-0 w-full shrink-0 border-line bg-surface md:block md:w-80 md:border-r ${
            requestedId ? "hidden" : "block"
          }`}
        >
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
          {displayEmails.length > 0 ? (
            <InboxList
              emails={displayEmails}
              selectedEmailId={selectedEmailId}
              onSelectEmail={handleSelectEmail}
            />
          ) : null}
          <LoadOlderEmails
            hasNextPage={emails.hasNextPage}
            isFetchingNextPage={emails.isFetchingNextPage}
            fetchNextPage={emails.fetchNextPage}
          />
        </aside>

        <section
          className={`min-h-0 min-w-0 flex-1 bg-surface-muted md:block ${requestedId ? "block" : "hidden"}`}
        >
          <EmailDetailPanel email={email} workflow={workflow} onBack={backToInbox} />
        </section>
      </>
    </AppShell>
  );
}
