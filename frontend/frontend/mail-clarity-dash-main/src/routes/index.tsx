import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import InboxList from "../components/InboxList";
import EmailDetailPanel from "../components/EmailDetailPanel";
import AppShell from "../components/AppShell";
import { PageEmpty, PageError, PageLoading } from "../components/PageState";
import { useEmail, useEmails, useSession } from "../lib/queries";
import { useDraftWorkflow } from "../lib/useDraftWorkflow";

type InboxSearch = { email?: string };

export const Route = createFileRoute("/")({
  // ?email=<id> opens that email, so Sent and other lists can link straight to one.
  validateSearch: (search: Record<string, unknown>): InboxSearch => ({
    email: typeof search.email === "string" ? search.email : undefined,
  }),
  head: () => ({
    meta: [
      { title: "AIMail — AI inbox dashboard" },
      {
        name: "description",
        content:
          "AIMail dashboard: prioritized inbox, AI summaries, action items, and approved-only draft replies.",
      },
      { property: "og:title", content: "AIMail — AI inbox dashboard" },
      {
        property: "og:description",
        content:
          "Prioritized inbox with AI summaries, action items, and human-approved draft replies.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DashboardPage,
});

function DashboardPage() {
  const { t } = useTranslation();
  const { email: requestedId } = Route.useSearch();
  const emails = useEmails();
  const session = useSession();
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const selected = useEmail(selectedEmailId);

  // The detail call re-runs generation (~15s), so show the list row's copy until it lands.
  const listEmail = (emails.data ?? []).find((item) => item.id === selectedEmailId) ?? null;
  const email = selected.data ?? listEmail;
  const workflow = useDraftWorkflow(email);

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
        </aside>

        <section className="min-h-0 min-w-0 flex-1 bg-surface-muted">
          <EmailDetailPanel
            email={email}
            draft={workflow.draft}
            tone={workflow.tone}
            onDraftChange={workflow.setDraft}
            onToneChange={(_emailId, tone) => workflow.regenerate(tone)}
            onRegenerate={() => workflow.regenerate()}
            onRefine={(_emailId, instruction) => workflow.refine(instruction)}
            onApproveSend={workflow.send}
            isRegenerating={workflow.isRegenerating}
            isRefining={workflow.isRefining}
            isSending={workflow.isSending}
            status={{
              ...workflow.status,
              isGenerating: selected.isLoading,
              isLoadFailed: selected.isError,
              onRetryLoad: () => void selected.refetch(),
            }}
          />
        </section>
      </>
    </AppShell>
  );
}
