import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import FilteredEmailList from "../components/FilteredEmailList";
import { isPendingDraft } from "../lib/drafts";
import { Page, pageMeta } from "../lib/pageMeta";

export const Route = createFileRoute("/drafts")({
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Drafts) }),
  component: DraftsPage,
});

/** Every reply the AI has written that has not gone out (specs/features/drafts-page.md). */
function DraftsPage() {
  const { t } = useTranslation();
  return (
    <AppShell>
      <FilteredEmailList
        heading={t("drafts.heading")}
        description={t("drafts.description")}
        label={t("drafts.label")}
        emptyTitle={t("drafts.emptyTitle")}
        emptyHint={t("drafts.emptyHint")}
        filter={isPendingDraft}
        timestampOf={(email) => email.timestamp}
        byConversation
      />
    </AppShell>
  );
}
