import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import ComposeDraftList from "../components/ComposeDraftList";
import ComposeEditor from "../components/ComposeEditor";
import { InlineAlert } from "../components/InlineMessages";
import { PageEmpty, PageError, PageLoading } from "../components/PageState";
import { button } from "../components/variants";
import { errorMessage } from "../lib/api/errors";
import { Page, pageMeta } from "../lib/pageMeta";
import { useComposeDraftQuery, useComposeList, useCreateComposeDraft } from "../lib/queries";
import { cn } from "../lib/utils";

type ComposeSearch = { draft?: string };

export const Route = createFileRoute("/compose")({
  // ?draft=<id> opens that draft, so a reload or a shared link comes back to it.
  validateSearch: (search: Record<string, unknown>): ComposeSearch => ({
    draft: typeof search.draft === "string" ? search.draft : undefined,
  }),
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Compose) }),
  component: ComposePage,
});

function ComposePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { draft: draftId } = Route.useSearch();
  const list = useComposeList();
  const create = useCreateComposeDraft();
  const open = (id?: string) =>
    void navigate({ to: "/compose", search: id === undefined ? {} : { draft: id } });
  const isEmpty = list.data?.drafts.length === 0 && list.data.sent.length === 0;

  return (
    <AppShell>
      <>
        {/* A phone shows the list until a draft is opened (?draft=), then only the draft. */}
        <aside
          className={`relative min-h-0 w-full shrink-0 flex-col overflow-y-auto border-line bg-surface md:flex md:w-80 md:border-r ${
            draftId ? "hidden" : "flex"
          }`}
        >
          <header className="space-y-3 p-4">
            <div>
              <h1 className="text-xl font-semibold text-fg">{t("compose.heading")}</h1>
              <p className="mt-1 text-sm text-fg-muted">{t("compose.description")}</p>
            </div>
            <button
              type="button"
              disabled={create.isPending}
              onClick={() => create.mutate({}, { onSuccess: (draft) => open(draft.id) })}
              className={cn(button({ intent: "primary", size: "md" }), "w-full gap-1.5")}
            >
              <Plus aria-hidden className="size-4" />
              {create.isPending ? t("compose.creating") : t("compose.newEmail")}
            </button>
            {create.isError ? (
              <InlineAlert size="xs">
                {errorMessage(create.error, t, "compose.failed.create")}
              </InlineAlert>
            ) : null}
          </header>
          {list.isPending ? <PageLoading label={t("compose.heading")} /> : null}
          {list.isError ? (
            <PageError
              label={t("compose.heading")}
              error={list.error}
              onRetry={() => void list.refetch()}
            />
          ) : null}
          {isEmpty ? (
            <PageEmpty title={t("compose.emptyTitle")} hint={t("compose.emptyHint")} />
          ) : null}
          {list.data && !isEmpty ? (
            <ComposeDraftList list={list.data} selectedId={draftId} />
          ) : null}
        </aside>

        <section
          className={`relative min-h-0 min-w-0 flex-1 bg-surface-muted md:block ${draftId ? "block" : "hidden"}`}
        >
          {draftId ? (
            <ComposeDraftPane key={draftId} id={draftId} onClose={() => open()} />
          ) : (
            <div className="flex h-full items-center justify-center p-8 text-center text-sm text-fg-subtle">
              {t("compose.pickHint")}
            </div>
          )}
        </section>
      </>
    </AppShell>
  );
}

function ComposeDraftPane({ id, onClose }: { id: string; onClose: () => void }) {
  const { t } = useTranslation();
  const draft = useComposeDraftQuery(id);
  if (draft.isPending) return <PageLoading label={t("compose.heading")} />;
  if (draft.isError) {
    return (
      <PageError
        label={t("compose.heading")}
        error={draft.error}
        onRetry={() => void draft.refetch()}
      />
    );
  }
  return <ComposeEditor draft={draft.data} onBack={onClose} onDeleted={onClose} />;
}
